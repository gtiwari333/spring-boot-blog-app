#!/usr/bin/env python3
"""
JFR (Java Flight Recorder) Startup Analyzer
============================================
Analyzes one or two JFR recordings to identify startup bottlenecks and
compare before/after optimizations.

Usage:
  python3 jfr-analyzer.py <file.jfr>                 # Single file analysis
  python3 jfr-analyzer.py <before.jfr> <after.jfr>   # Before/after comparison

Requirements:
  - Java 21+ with `jfr` CLI tool on PATH
  - Python 3.8+

Output:
  - CPU execution hot spots (method-level and full stack traces)
  - Memory allocation hotspots by type and allocation site
  - GC / heap behavior timeline
  - Wall clock sleeping / thread idle analysis
  - Side-by-side comparison (when two files are provided)


What It Analyzes

    ┌─────────────────────┬────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
    │       Section       │        Data Source         │                                                     What It Shows                                                      │
    ├─────────────────────┼────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │ CPU Hotspots        │ jdk.ExecutionSample        │ Top 30 hot leaf methods, thread distribution, top 20 full stack signatures                                             │
    ├─────────────────────┼────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Allocation Hotspots │ jdk.ObjectAllocationSample │ Top 40 allocation types by weight, top byte[] allocation sites (stack traces)                                          │
    ├─────────────────────┼────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │ GC/Heap Timeline    │ jdk.GCHeapSummary          │ Heap growth over time, peak usage                                                                                      │
    ├─────────────────────┼────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Wall Clock Sleeping │ profiler.WallClockSleeping │ Idle/wait time by thread, longest individual sleep events                                                              │
    ├─────────────────────┼────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Comparison Mode     │ Both files                 │ Delta tables for allocation types (with ELIMINATED markers), CPU method deltas, GC event reduction, sleep time changes │
    └─────────────────────┴────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘


Typical startup bottlenecks this tool reveals:

  CPU Hotspots:
    - ClassLoader.defineClass1    →  Too many classes being loaded; use CDS or trim dependencies
    - Inflater.inflateBytesBytes  →  JAR decompression overhead; use CDS to bypass
    - Object.clone                →  Reflection-driven cloning; use AOT to pre-compute metadata
    - AnnotationsScanner.*        →  Spring annotation scanning; use spring-context-indexer

  Allocation Hotspots:
    - byte[] (Resource.getBytes)  →  Class file bytes from JARs; use CDS
    - TypeMappedAnnotations       →  Spring annotation model; use lazy-init + AOT
    - reflect/Field, reflect/Method → Reflection metadata; use AOT
    - ASM SymbolTable$Entry       →  Bytecode parsing; use AOT

  What to look for in the comparison:
    - Types marked "ELIMINATED"   →  The optimization completely removed this cost
    - Large negative deltas       →  The optimization significantly reduced this cost
    - Positive deltas             →  May indicate shifted work (e.g. lazy init defers to later)

"""

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                         HELPER FUNCTIONS                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


def jfr_print_json(jfr_file: str, events: str) -> dict:
    """
    Invoke the JDK's `jfr` CLI tool to extract events as JSON.

    The `jfr` tool is part of the JDK distribution (since JDK 14+).
    It reads the binary .jfr file and outputs event data in JSON or plain text.

    We use --json mode for events that carry numeric data (allocation weights,
    durations, heap sizes) because JSON preserves exact values.  The output
    is pretty-printed (multi-line with indentation), so we parse the whole
    stdout string rather than filtering individual lines.

    Parameters:
        jfr_file: Path to the .jfr recording.
        events:   Comma-separated JFR event type names (e.g. "jdk.ExecutionSample").

    Returns:
        Parsed dict with structure: {"recording": {"events": [...]}}
    """
    result = subprocess.run(
        ["jfr", "print", "--events", events, "--json", str(jfr_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    # JSON is written to stdout; JAVA_TOOL_OPTIONS warnings go to stderr
    output = result.stdout.strip()
    if not output:
        # Some older JDK builds route JSON to stderr — fall back
        output = result.stderr.strip()
    return json.loads(output)


def jfr_print_text(jfr_file: str, events: str) -> str:
    """
    Invoke the JDK's `jfr` CLI to extract events as human-readable text.

    We use text mode for ExecutionSample (CPU) events because the text format
    includes full stack traces in a compact, easy-to-parse layout.  Each event
    block starts with "jdk.ExecutionSample {" followed by key=value lines and a
    "stackTrace = [...]" section.

    Parameters:
        jfr_file: Path to the .jfr recording.
        events:   JFR event type name (typically just one type for text mode).

    Returns:
        Raw text output from the jfr tool.
    """
    result = subprocess.run(
        ["jfr", "print", "--events", events, str(jfr_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.stdout.strip()


def parse_duration_iso(dur) -> float:
    """
    Parse a JFR duration value into milliseconds.

    The JFR JSON output uses ISO 8601 duration strings for some fields
    (e.g. "PT0.328702567S" = 0.329 seconds).  Other fields use raw
    nanosecond integers.  This function handles both.

    Returns:
        Duration in milliseconds (float).
    """
    if dur is None or dur == 0:
        return 0.0
    if isinstance(dur, (int, float)):
        # Raw value — assume nanoseconds (JFR convention for duration fields)
        return float(dur) / 1_000_000
    if isinstance(dur, str):
        # ISO 8601 pattern: PT<seconds>S
        m = re.match(r"PT([\d.]+)S", dur)
        if m:
            return float(m.group(1)) * 1000
    return 0.0


def format_bytes(n: int) -> str:
    """
    Format a byte count into a human-readable string with appropriate units.

    >>> format_bytes(291535472)
    '278.0 MB'
    >>> format_bytes(4096)
    '4.0 KB'
    """
    if abs(n) < 1024:
        return f"{n} B"
    for unit in ["KB", "MB", "GB"]:
        n /= 1024.0
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}"
    return f"{n:,.1f} TB"


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                     JFR DATA MODEL (JfrAnalysis)                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


class JfrAnalysis:
    """
    Parsed and queryable data from a single JFR recording.

    On construction, this class shells out to the `jfr` CLI to extract
    five event types from the binary .jfr file:

    1. jdk.ExecutionSample (text mode)
       ─────────────────────────────────
       Periodic thread dumps taken by the JFR profiler.  Each sample captures
       which method a thread was executing at that instant.  The leaf (top)
       frame is the actual method running; frames below it show the call chain.

       Key insight: If 111 out of 587 samples (18.9%) land in
       ClassLoader.defineClass1, that method consumed ~19% of CPU time during
       the recording.  This is our primary CPU hotspot detector.

    2. jdk.ObjectAllocationSample (JSON mode)
       ──────────────────────────────────────
       Sampled object allocations with class name, weight (bytes allocated),
       and allocation-site stack trace.  Unlike TLAB events which track every
       allocation, these are sampled (configurable rate).  The "weight" field
       tells us how many bytes were allocated by that code path.

       Key insight: If byte[] accounts for 292 MB (46%) of 636 MB total, and
       the top allocation site is Resource.getBytes (class loading), then
       class loading is the #1 memory churn source.

    3. jdk.ObjectAllocationInNewTLAB (JSON mode)
       ─────────────────────────────────────────
       Allocation events for new TLAB (Thread-Local Allocation Buffer)
       creation.  Supplementary to ObjectAllocationSample — these fire when
       a thread exhausts its TLAB and requests a new one from the heap.
       Useful for confirming allocation pressure patterns.

    4. profiler.WallClockSleeping (JSON mode)
       ───────────────────────────────────────
       Tracks periods when threads are idle/sleeping rather than running.
       High sleep time on the main thread during startup would indicate
       I/O waits or lock contention.  The duration and samplesCount fields
       tell us how long and how consistently a thread was blocked.

       Key insight: If DestroyJavaVM (main thread) has low sleep, the app
       is CPU-bound.  If it has high sleep in jdbc/net stacks, there's an
       I/O bottleneck.

    5. jdk.GCHeapSummary (JSON mode)
       ──────────────────────────────
       Periodic heap snapshots recording eden, survivor, and old-gen usage.
       We use this to track heap growth over the recording window and
       identify whether GC pressure is a bottleneck.

       Key insight: Heap growing from 15 MB to 60 MB in 17s means lots of
       objects are being created and retained during startup.  Coupled with
       allocation data, this points to what's filling the heap.

    Attributes:
        file:            Path to the .jfr file.
        name:            Stem of the filename (used in report headers).
        cpu_samples:     List of dicts with keys: thread, state, frames.
        alloc_samples:   Raw JSON event list from ObjectAllocationSample.
        tlab_samples:    Raw JSON event list from ObjectAllocationInNewTLAB.
        sleep_events:    Raw JSON event list from WallClockSleeping.
        gc_events:       Raw JSON event list from GCHeapSummary.
    """

    def __init__(self, jfr_file: str):
        self.file = jfr_file
        self.name = Path(jfr_file).stem

        # Parsed data — populated by _load()
        self.cpu_samples: list[dict] = []     # CPU execution samples
        self.alloc_samples: list[dict] = []   # Object allocation samples
        self.tlab_samples: list[dict] = []    # TLAB allocation events
        self.sleep_events: list[dict] = []    # Wall clock sleep events
        self.gc_events: list[dict] = []       # GC heap summary snapshots

        self._load()

    # ── Data Loading ──────────────────────────────────────────────────────

    def _load(self):
        """
        Extract all five event types from the JFR file.

        Each extraction is wrapped in try/except because:
        - The JFR may not have been configured to capture that event type.
        - The jfr CLI tool version may not support that event type.
        - We don't want one missing event type to block the entire analysis.

        CPU events use text mode (richer stack traces, easier to regex-parse).
        All other events use JSON mode (preserves numeric precision).
        """
        print(f"[INFO] Loading {self.file} ...", file=sys.stderr)

        # (1) CPU execution samples — text mode for full stack traces
        #     The text format is: "jdk.ExecutionSample { ... stackTrace = [...] }"
        #     which is more compact and easier to parse than the JSON equivalent.
        try:
            text = jfr_print_text(self.file, "jdk.ExecutionSample")
            self._parse_cpu_text(text)
        except Exception as e:
            print(f"  [WARN] CPU samples: {e}", file=sys.stderr)

        # (2) Object allocation samples — JSON for accurate weight (byte) values
        #     These are the primary data for memory churn analysis.
        try:
            data = jfr_print_json(self.file, "jdk.ObjectAllocationSample")
            self.alloc_samples = data.get("recording", {}).get("events", [])
        except Exception as e:
            print(f"  [WARN] Allocation samples: {e}", file=sys.stderr)

        # (3) TLAB allocations — JSON; supplementary allocation data
        #     Not always enabled in JFR recordings, so we silently skip.
        try:
            data = jfr_print_json(self.file, "jdk.ObjectAllocationInNewTLAB")
            self.tlab_samples = data.get("recording", {}).get("events", [])
        except Exception:
            pass  # TLAB data is optional

        # (4) Wall clock sleeping — JSON; tracks thread idle/wait time
        try:
            data = jfr_print_json(self.file, "profiler.WallClockSleeping")
            self.sleep_events = data.get("recording", {}).get("events", [])
        except Exception as e:
            print(f"  [WARN] Sleep events: {e}", file=sys.stderr)

        # (5) GC heap summaries — JSON; heap usage snapshots over time
        try:
            data = jfr_print_json(self.file, "jdk.GCHeapSummary")
            self.gc_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass  # GC data is optional

    def _parse_cpu_text(self, text: str):
        """
        Parse the human-readable ExecutionSample output into structured dicts.

        The text format looks like this (one block per sample):

            jdk.ExecutionSample {
              startTime = 22:07:14.629
              sampledThread = "DestroyJavaVM" (javaThreadId = 72)
              state = "STATE_RUNNABLE"
              stackTrace = [
                javax.management.ObjectName.<clinit>() line: 332
                com.sun.jmx.mbeanserver.Util.newObjectName(String) line: 48
                ...
              ]
            }

        We split on "\njdk.ExecutionSample {" to isolate each block, then
        use regex to extract the thread name, thread state, and stack frames.
        The first (index 0) frame is the leaf — the actual method on CPU.
        Frames below it are the call chain (caller → caller's caller → ...).

        Why text mode instead of JSON for CPU data?
        ───────────────────────────────────────────
        The JSON format for stack traces is deeply nested (method → type → package
        → module → classloader), making it 5-10x larger and slower to parse.
        The text format keeps stack traces flat (one line per frame), which is
        both faster to parse and easier to regex.
        """
        # Each sample block starts with "jdk.ExecutionSample {" on its own line
        blocks = re.split(r"\njdk\.ExecutionSample \{", text)

        for block in blocks[1:]:  # Skip text before the first block
            sample: dict[str, str | list[str]] = {}

            # Extract the thread name: sampledThread = "DestroyJavaVM" (...)
            tm = re.search(r'sampledThread\s*=\s*"([^"]+)"', block)
            sample["thread"] = tm.group(1) if tm else "unknown"

            # Extract the thread state: state = "STATE_RUNNABLE"
            sm = re.search(r'state\s*=\s*"([^"]+)"', block)
            sample["state"] = sm.group(1) if sm else "?"

            # Extract the stack trace frames from the [...] block.
            # re.DOTALL is needed because stack traces span multiple lines.
            stack_sec = re.search(r"stackTrace\s*=\s*\[(.*?)\]", block, re.DOTALL)
            if stack_sec:
                # Each frame is one line; strip whitespace, skip empty lines
                sample["frames"] = [
                    f.strip()
                    for f in stack_sec.group(1).strip().split("\n")
                    if f.strip()
                ]
            else:
                sample["frames"] = []

            self.cpu_samples.append(sample)

    # ── CPU Accessors ─────────────────────────────────────────────────────
    # These methods aggregate the CPU sample data for the reports.

    def cpu_method_counts(self) -> Counter:
        """
        Count occurrences of each leaf (top-of-stack) method.

        The leaf frame is the method that was actually executing when the
        sample was taken.  This tells us WHERE CPU time is spent.

        Returns a Counter mapping method signatures to sample counts.
        Example: {"java.lang.ClassLoader.defineClass1(...)": 111, ...}
        """
        c: Counter[str] = Counter()
        for s in self.cpu_samples:
            if s["frames"]:
                c[s["frames"][0]] += 1
        return c

    def cpu_thread_counts(self) -> Counter:
        """
        Count samples per thread to show which threads are doing the work.

        For startup analysis, this is critical: if the main thread
        (DestroyJavaVM) has 88%+ of samples, the app is essentially
        single-threaded during startup and won't benefit from more cores.
        """
        c: Counter[str] = Counter()
        for s in self.cpu_samples:
            c[s["thread"]] += 1
        return c

    def cpu_stack_sigs(self, depth: int = 5) -> Counter:
        """
        Build full stack signatures (top N frames joined by " -> ").

        The leaf frame alone tells you WHAT is hot.  The full stack tells
        you WHY — what higher-level operation is driving that hotspot.

        Example signature:
          "Object.clone() -> Class.getInterfaces() ->
           AnnotationsScanner.processClassHierarchy() -> ..."

        This reveals that Object.clone() is hot because Spring is walking
        class hierarchies to find annotations — actionable insight.
        """
        c: Counter[str] = Counter()
        for s in self.cpu_samples:
            sig = " -> ".join(f[:90] for f in s["frames"][:depth])
            c[sig] += 1
        return c

    # ── Allocation Accessors ──────────────────────────────────────────────

    def alloc_by_class(self) -> Counter:
        """
        Sum allocation weight (bytes) by object class name.

        JFR's ObjectAllocationSample events record:
          - objectClass: The type being allocated (e.g. "[B" for byte[]).
          - weight:      How many bytes were allocated by this allocation site.

        This method aggregates by class name to answer:
        "Which types account for the most memory churn during startup?"

        Common top offenders in Spring Boot startup:
          - [B (byte[])           → class file bytes, I/O buffers
          - TypeMappedAnnotations → Spring's annotation metadata model
          - reflect/Field, Method → reflection metadata
          - ASM SymbolTable$Entry → bytecode parsing structures
        """
        c: Counter[str] = Counter()
        for e in self.alloc_samples:
            v = e["values"]
            oc = v.get("objectClass", {})
            # objectClass can be a dict with a 'name' key, or a plain string
            cls_name = oc.get("name", "unknown") if isinstance(oc, dict) else str(oc)
            weight = v.get("weight", 0) or 0
            c[cls_name] += weight
        return c

    def alloc_stack_sigs(self, class_filter: str | None = None, depth: int = 4) -> Counter:
        """
        Build allocation stack signatures, optionally filtered by class name.

        This answers: "WHERE are byte[] arrays being allocated from?"
        By filtering on class_filter="[B" we see the allocation sites
        (stack traces) responsible for the #1 memory churn category.

        Parameters:
            class_filter: If set, only include allocations of this type.
                          Use "[B" for byte arrays, "java/lang/String" for strings, etc.
            depth:        Number of stack frames to include in the signature.
        """
        c: Counter[str] = Counter()
        for e in self.alloc_samples:
            v = e["values"]
            oc = v.get("objectClass", {})
            cls_name = oc.get("name", "unknown") if isinstance(oc, dict) else str(oc)
            # Skip if a filter is active and this allocation doesn't match
            if class_filter and class_filter not in cls_name:
                continue
            weight = v.get("weight", 0) or 0
            frames = v.get("stackTrace", {}).get("frames", [])
            if frames:
                # Build signature: "pkg.Class.method -> pkg.Class.method -> ..."
                sig = " -> ".join(
                    f"{f['method']['type']['name']}.{f['method']['name']}"[:80]
                    for f in frames[:depth]
                )
                c[sig] += weight
        return c

    # ── Sleep / Idle Accessors ────────────────────────────────────────────

    def sleep_by_thread(self) -> Counter:
        """
        Sum idle/sleep duration (ms) by thread.

        WallClockSleeping events record periods when a thread is NOT on CPU —
        it could be blocked on I/O, waiting for a lock, or deliberately sleeping.
        High sleep on the main thread during startup often means I/O waits
        (database connections, network calls, file reads).

        Returns a Counter: thread_name → total_sleep_milliseconds.
        """
        c: Counter[str] = Counter()
        for e in self.sleep_events:
            v = e["values"]
            t = v.get("eventThread", {}).get("javaName", "?")
            c[t] += parse_duration_iso(v.get("duration", 0))
        return c

    def sleep_longest(self, n: int = 15) -> list[tuple[float, str, str, int]]:
        """
        Return the N longest individual sleep events.

        While sleep_by_thread() shows aggregates, this method reveals
        individual blocking episodes — useful for spotting one-off delays
        like a slow DB connection or a DNS resolution timeout.

        Returns:
            List of (duration_ms, thread_name, top_stack_frame, sample_count).
        """
        sorted_events = sorted(
            self.sleep_events,
            key=lambda e: parse_duration_iso(e["values"].get("duration", 0)),
            reverse=True,
        )
        result: list[tuple[float, str, str, int]] = []
        for e in sorted_events[:n]:
            v = e["values"]
            dur_ms = parse_duration_iso(v.get("duration", 0))
            frames = v.get("stackTrace", {}).get("frames", [])
            top_frame = (
                f"{frames[0]['method']['type']['name']}.{frames[0]['method']['name']}"
                if frames
                else "unknown"
            )
            thread = v.get("eventThread", {}).get("javaName", "?")
            samples = v.get("samplesCount", "?")
            result.append((dur_ms, thread, top_frame, samples))
        return result

    # ── GC / Heap Accessors ───────────────────────────────────────────────

    def gc_heap_series(self) -> list[tuple[str, float]]:
        """
        Return a time series of heap usage: (timestamp_iso8601, heap_used_mb).

        GCHeapSummary events are periodic snapshots of Eden, Survivor, and
        Old generation usage.  Plotting these over time shows the heap growth
        curve during startup and whether GC is keeping up.

        A rapidly growing heap with few GC events means lots of short-lived
        allocations; a flat heap means GC is working hard to reclaim memory.
        """
        return [
            (
                e["values"].get("startTime", "")[:19],   # ISO timestamp
                e["values"].get("heapUsed", 0) / 1024 / 1024,  # MB
            )
            for e in self.gc_events
        ]

    # ── Convenience Properties ────────────────────────────────────────────

    @property
    def total_alloc_bytes(self) -> int:
        """Total bytes allocated across all sampled allocation events."""
        return sum(self.alloc_by_class().values())

    @property
    def cpu_sample_count(self) -> int:
        """Number of CPU execution samples captured."""
        return len(self.cpu_samples)

    @property
    def alloc_sample_count(self) -> int:
        """Number of allocation samples captured."""
        return len(self.alloc_samples)

    @property
    def total_sleep_ms(self) -> float:
        """Total wall-clock sleep time across all threads, in milliseconds."""
        return sum(self.sleep_by_thread().values())


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                         REPORT RENDERING                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# Width of the section separator lines — kept wide enough for stack traces
SECTION_WIDTH = 95


def print_header(title: str):
    """Print a centered, double-lined section header."""
    print()
    print("=" * SECTION_WIDTH)
    print(f"{title:^{SECTION_WIDTH}}")
    print("=" * SECTION_WIDTH)


def report_single(analysis: JfrAnalysis):
    """
    Print a complete analysis report for a single JFR file.

    The report has five sections, each corresponding to one JFR event type:

    1. CPU EXECUTION HOTSPOTS
       ──────────────────────
       - Top 30 hot leaf methods (where CPU time is spent)
       - Thread distribution (which threads do the work)
       - Top 20 full stack signatures (WHY those methods are hot)

       Interpretation:
         If ClassLoader.defineClass1 is #1 (typically 15-20% during startup),
         the app is spending most of its time loading classes from JARs.
         Solution: CDS archive or trim dependencies.

         If Inflater.inflateBytesBytes is #2 (typically 5-8% during startup),
         JAR/ZIP decompression is a significant cost.
         Solution: CDS archive.

         If AnnotationsScanner.* appears, Spring is scanning annotations.
         Solution: spring-context-indexer or AOT processing.

    2. MEMORY ALLOCATION HOTSPOTS
       ──────────────────────────
       - Top 40 allocation types by total bytes allocated
       - Top 20 byte[] allocation sites (stack traces)

       Interpretation:
         byte[] at 40-50% with Resource.getBytes stacks → class loading churn.
         TypeMappedAnnotations at 3-5% → Spring annotation model building.
         reflect/Field + reflect/Method → reflection metadata.

    3. TOP byte[] ALLOCATION SITES
       ───────────────────────────
       - Detailed breakdown of WHERE byte arrays are allocated from.
         This is the most actionable allocation data because byte[]
         dominates startup memory churn.

    4. GC / HEAP TIMELINE
       ───────────────────
       - Heap usage snapshots over the recording window.

    5. WALL CLOCK SLEEPING
       ────────────────────
       - Idle/wait time by thread.
       - Longest individual sleep events (potential I/O or lock bottlenecks).
    """
    print_header(f"JFR ANALYSIS: {analysis.name}")

    # ── Section 1: CPU Hotspots ───────────────────────────────────────────
    print_header("CPU EXECUTION HOTSPOTS")
    methods = analysis.cpu_method_counts()
    total = sum(methods.values())
    print(f"\n  Total samples: {total}")
    print(f"\n  {'Top 30 Hot Leaf Methods':^80}")
    print(f"  {'Method':<70} {'Count':>7} {'Pct':>7}")
    print(f"  {'-'*70} {'-'*7} {'-'*7}")
    for method, count in methods.most_common(30):
        pct = count / total * 100
        print(f"  {method[:68]:<68} {count:>7d} {pct:>6.1f}%")

    # Thread distribution — is the app single-threaded or parallel at startup?
    threads = analysis.cpu_thread_counts()
    print(f"\n  {'Thread Distribution':^80}")
    print(f"  {'Thread':<50} {'Count':>7} {'Pct':>7}")
    print(f"  {'-'*50} {'-'*7} {'-'*7}")
    for t, c in threads.most_common(15):
        pct = c / total * 100
        print(f"  {t[:48]:<48} {c:>7d} {pct:>6.1f}%")

    # ── Section 1b: CPU Stack Signatures ──────────────────────────────────
    # Full stacks provide context: the leaf method says WHAT, the stack says WHY.
    print_header("TOP CPU STACK SIGNATURES (top 5 frames)")
    sigs = analysis.cpu_stack_sigs(depth=5)
    for sig, count in sigs.most_common(20):
        pct = count / total * 100
        print(f"\n  [{count}x, {pct:.1f}%]")
        for line in sig.split(" -> "):
            print(f"    {line}")

    # ── Section 2: Allocation Hotspots ────────────────────────────────────
    print_header("MEMORY ALLOCATION HOTSPOTS")
    alloc = analysis.alloc_by_class()
    total_alloc = sum(alloc.values())
    print(f"\n  Total allocation: {format_bytes(total_alloc)} ({total_alloc/1024/1024:.1f} MB)")
    print(f"  Sample count: {analysis.alloc_sample_count}")

    print(f"\n  {'Top 40 Allocation Types':^80}")
    print(f"  {'Type':<55} {'Bytes':>14} {'Pct':>7}")
    print(f"  {'-'*55} {'-'*14} {'-'*7}")
    for cls, w in alloc.most_common(40):
        pct = w / total_alloc * 100
        print(f"  {cls[:53]:<53} {w:>14,d} {pct:>6.1f}%")

    # ── Section 2b: byte[] Allocation Sites ───────────────────────────────
    # byte[] is almost always #1 (loading class files, I/O buffers).
    # Showing WHERE those allocations come from tells us what to optimize.
    print_header("TOP byte[] ALLOCATION SITES")
    byte_stacks = analysis.alloc_stack_sigs(class_filter="[B", depth=4)
    total_byte = sum(byte_stacks.values())
    print(f"\n  Total byte[]: {format_bytes(total_byte)} ({total_byte/1024/1024:.1f} MB)")
    for sig, w in byte_stacks.most_common(20):
        pct = w / total_byte * 100
        print(f"\n  {w:>12,d} ({pct:.1f}%)")
        for line in sig.split(" -> "):
            print(f"    {line}")

    # ── Section 3: GC / Heap Timeline ─────────────────────────────────────
    print_header("GC / HEAP TIMELINE")
    heap = analysis.gc_heap_series()
    if heap:
        peaks = [h[1] for h in heap]
        print(f"\n  Events: {len(heap)}")
        print(f"  Heap range: {min(peaks):.1f} MB → {max(peaks):.1f} MB (peak)")
        print(f"\n  {'Timestamp':<22} {'Heap':>10}")
        print(f"  {'-'*22} {'-'*10}")
        for ts, mb in heap:
            print(f"  {ts:<22} {mb:>8.1f} MB")

    # ── Section 4: Wall Clock Sleeping ────────────────────────────────────
    print_header("WALL CLOCK SLEEPING (Idle/Wait Time)")
    sleep_threads = analysis.sleep_by_thread()
    total_sleep = sum(sleep_threads.values())
    print(f"\n  Total sleep across all threads: {total_sleep/1000:.1f}s")
    print(f"  Events: {len(analysis.sleep_events)}")

    print(f"\n  {'By Thread':^70}")
    print(f"  {'Thread':<45} {'Time (ms)':>12} {'Pct':>7}")
    print(f"  {'-'*45} {'-'*12} {'-'*7}")
    for t, d in sleep_threads.most_common(20):
        pct = d / total_sleep * 100 if total_sleep else 0
        print(f"  {t[:43]:<43} {d:>12,.0f} {pct:>6.1f}%")

    # Show the longest individual sleep events for bottleneck diagnosis
    longest = analysis.sleep_longest(15)
    if longest:
        print(f"\n  {'Longest Individual Sleep Events':^80}")
        print(f"  {'Duration':>10} {'Samples':>8} {'Thread':<30} {'Top Frame':<40}")
        print(f"  {'-'*10} {'-'*8} {'-'*30} {'-'*40}")
        for dur_ms, thread, top_frame, samples in longest:
            print(f"  {dur_ms:>10,.0f} ms {samples:>8} {thread[:28]:<28} {top_frame[:38]:<38}")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                      BEFORE/AFTER COMPARISON                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


def report_comparison(before: JfrAnalysis, after: JfrAnalysis):
    """
    Print a side-by-side comparison of two JFR recordings.

    This is the primary tool for validating optimizations: you capture one
    JFR before making changes and one after, then run this comparison to
    quantify the impact.

    The comparison has five sections:

    1. ALLOCATION COMPARISON
       ─────────────────────
       For each allocation type, shows the before/after byte counts and delta.
       Types that were significant before but dropped to zero after are
       flagged with "◀◀ ELIMINATED".  This is the most reliable signal that
       your optimization worked — if TypeMappedAnnotations went from 21 MB
       to 0, lazy init + spring-context-indexer did their job.

    2. CPU EXECUTION SAMPLE COMPARISON
       ───────────────────────────────
       Shows before/after sample counts for hot methods.  Methods that
       disappeared or dropped >50% are flagged with "◀◀".

    3. THREAD DISTRIBUTION COMPARISON
       ──────────────────────────────
       Shows whether the threading profile changed (e.g., did more work
       shift to background threads after lazy init?).

    4. GC / HEAP COMPARISON
       ─────────────────────
       Compares heap pressure — fewer GC events and lower peak usage
       indicate reduced allocation churn.

    5. WALL CLOCK SLEEPING COMPARISON
       ──────────────────────────────
       Shows whether sleep/idle patterns changed.

    Interpreting the comparison:
      - "ELIMINATED" markers → The optimization completely removed this cost.
      - Large negative % → The optimization significantly reduced this cost.
      - Positive % deltas → May indicate shifted/deferred work.  For example,
        with lazy init, Class allocations may go UP because classes are now
        loaded on first access instead of at startup.
    """
    print_header(f"BEFORE vs AFTER COMPARISON")
    print(f"  Before: {before.name}")
    print(f"  After:  {after.name}")

    # ── Section 1: Allocation Comparison ──────────────────────────────────
    print_header("ALLOCATION COMPARISON")
    old_alloc = before.alloc_by_class()
    new_alloc = after.alloc_by_class()
    old_total = sum(old_alloc.values())
    new_total = sum(new_alloc.values())

    # Summary row
    print(f"\n  {'Metric':<48} {'Before':>15} {'After':>15} {'Change':>15}")
    print(f"  {'-'*48} {'-'*15} {'-'*15} {'-'*15}")
    print(f"  {'Total allocation':<48} {format_bytes(old_total):>15} {format_bytes(new_total):>15} {format_bytes(new_total-old_total):>15}")
    print(f"  {'Total (MB)':<48} {old_total/1024/1024:>14.1f} MB {new_total/1024/1024:>14.1f} MB {(new_total-old_total)/1024/1024:>+14.1f} MB")
    print(f"  {'Allocation samples':<48} {before.alloc_sample_count:>15,d} {after.alloc_sample_count:>15,d} {after.alloc_sample_count-before.alloc_sample_count:>+15,d}")

    # Per-type delta table, sorted by "before" weight (most impactful first)
    print(f"\n  {'Top Allocation Types Comparison':^95}")
    print(f"  {'Type':<52} {'Before':>13} {'After':>13} {'Delta':>14}")
    print(f"  {'-'*52} {'-'*13} {'-'*13} {'-'*14}")

    all_types = set(list(old_alloc.keys()) + list(new_alloc.keys()))
    for t in sorted(all_types, key=lambda t: old_alloc.get(t, 0), reverse=True)[:40]:
        o = old_alloc.get(t, 0)
        n = new_alloc.get(t, 0)
        delta = n - o
        if o == 0 and n == 0:
            continue
        pct = (delta / o * 100) if o else (float("inf") if n > 0 else 0)
        # Flag types that were significant (>1 MB) and completely disappeared
        marker = " ◀◀ ELIMINATED" if o > 1_000_000 and n == 0 else ""
        print(f"  {t[:50]:<50} {o:>13,d} {n:>13,d} {delta:>+14,d} ({pct:+.0f}%){marker}")

    # ── Section 2: CPU Comparison ─────────────────────────────────────────
    print_header("CPU EXECUTION SAMPLE COMPARISON")
    old_methods = before.cpu_method_counts()
    new_methods = after.cpu_method_counts()
    old_cpu_total = sum(old_methods.values())
    new_cpu_total = sum(new_methods.values())

    print(f"\n  Before: {old_cpu_total} samples")
    print(f"  After:  {new_cpu_total} samples")
    if old_cpu_total:
        print(f"  Delta:  {new_cpu_total - old_cpu_total:+d} ({(1 - new_cpu_total/old_cpu_total)*100:+.1f}%)")

    print(f"\n  {'Top Hot Methods Comparison':^90}")
    print(f"  {'Method':<65} {'Before':>8} {'After':>8} {'Delta':>8}")
    print(f"  {'-'*65} {'-'*8} {'-'*8} {'-'*8}")

    all_methods = set(list(old_methods.keys()) + list(new_methods.keys()))
    for m in sorted(all_methods, key=lambda m: old_methods.get(m, 0), reverse=True)[:30]:
        o = old_methods.get(m, 0)
        n = new_methods.get(m, 0)
        delta = n - o
        # Flag methods that disappeared or dropped significantly (>50%)
        marker = " ◀◀" if (o > 2 and n == 0) or (o >= 5 and delta <= -o * 0.5) else ""
        print(f"  {m[:63]:<63} {o:>8} {n:>8} {delta:>+8}{marker}")

    # ── Section 2b: Thread Distribution Comparison ────────────────────────
    print(f"\n  {'Thread Distribution Comparison':^90}")
    print(f"  {'Thread':<40} {'Before':>8} {'After':>8} {'Delta':>8}")
    print(f"  {'-'*40} {'-'*8} {'-'*8} {'-'*8}")
    old_threads = before.cpu_thread_counts()
    new_threads = after.cpu_thread_counts()
    all_threads = set(list(old_threads.keys()) + list(new_threads.keys()))
    for t in sorted(all_threads, key=lambda t: old_threads.get(t, 0), reverse=True)[:15]:
        o = old_threads.get(t, 0)
        n = new_threads.get(t, 0)
        print(f"  {t[:38]:<38} {o:>8} {n:>8} {n-o:>+8}")

    # ── Section 3: GC Comparison ──────────────────────────────────────────
    print_header("GC / HEAP COMPARISON")
    old_heap = before.gc_heap_series()
    new_heap = after.gc_heap_series()
    if old_heap:
        print(f"\n  Before: {len(old_heap)} GC events, "
              f"heap {min(h[1] for h in old_heap):.1f} → {max(h[1] for h in old_heap):.1f} MB")
    else:
        print("  Before: no GC data")
    if new_heap:
        print(f"  After:  {len(new_heap)} GC events, "
              f"heap {min(h[1] for h in new_heap):.1f} → {max(h[1] for h in new_heap):.1f} MB")
    else:
        print("  After:  no GC data")
    if old_heap and new_heap and len(old_heap) > 0:
        print(f"  GC event reduction: {len(old_heap) - len(new_heap)} events "
              f"({(1 - len(new_heap)/len(old_heap))*100:.1f}%)")

    # ── Section 4: Sleep Comparison ───────────────────────────────────────
    print_header("WALL CLOCK SLEEPING COMPARISON")
    old_sleep = before.sleep_by_thread()
    new_sleep = after.sleep_by_thread()
    old_sleep_total = sum(old_sleep.values())
    new_sleep_total = sum(new_sleep.values())
    print(f"\n  Before: {len(before.sleep_events)} events, {old_sleep_total/1000:.1f}s total")
    print(f"  After:  {len(after.sleep_events)} events, {new_sleep_total/1000:.1f}s total")

    print(f"\n  {'Thread':<40} {'Before (ms)':>12} {'After (ms)':>12} {'Delta':>12}")
    print(f"  {'-'*40} {'-'*12} {'-'*12} {'-'*12}")
    all_sleep_threads = set(list(old_sleep.keys()) + list(new_sleep.keys()))
    for t in sorted(all_sleep_threads, key=lambda t: old_sleep.get(t, 0), reverse=True)[:15]:
        o = old_sleep.get(t, 0)
        n = new_sleep.get(t, 0)
        print(f"  {t[:38]:<38} {o:>12,.0f} {n:>12,.0f} {n-o:>+12,.0f}")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                            ENTRY POINT                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


def main():
    """
    Parse command-line arguments and dispatch to the appropriate report.

    Modes:
      - 1 argument:  Single-file analysis (full report).
      - 2 arguments: Before/after comparison (single reports + diff report).
      - 0 or >2:     Print usage and exit.
    """
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    files = sys.argv[1:]

    if len(files) == 1:
        # ── Single-file mode ──────────────────────────────────────────
        analysis = JfrAnalysis(files[0])
        report_single(analysis)

    elif len(files) == 2:
        # ── Comparison mode ───────────────────────────────────────────
        before = JfrAnalysis(files[0])
        after = JfrAnalysis(files[1])
        # Print individual reports first (detailed drill-down for each file)
        report_single(before)
        report_single(after)
        # Then the side-by-side comparison (highlighting deltas)
        report_comparison(before, after)

    else:
        print(
            "ERROR: Provide 1 JFR file (single analysis) or 2 JFR files (comparison).",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
