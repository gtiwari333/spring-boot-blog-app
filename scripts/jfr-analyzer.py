#!/usr/bin/env python3
"""
JFR (Java Flight Recorder) Startup Analyzer
============================================
Analyzes one or two JFR recordings to identify startup bottlenecks and
compare before/after optimizations.

Take a JFR recording from a running JVM app:
- JDK Mission Control (JMC) — a GUI front end for browsing recordings
- An IDE profiler (e.g., IntelliJ's built-in async-profiler integration)
- `jcmd <PID> JFR.start settings=profile name=<NAME>`  (attach to a running JVM)
- `java -XX:StartFlightRecording=settings=profile,filename=out.jfr -jar app.jar`
  (record from process launch — best for startup analysis)

Usage:
  python3 jfr-analyzer.py <file.jfr>                 # Single file analysis
  python3 jfr-analyzer.py <before.jfr> <after.jfr>   # Before/after comparison
  (add --markdown / -m to either form for Markdown-formatted output)

Requirements:
  - Java 17+ with the `jfr` CLI tool on PATH (some sections — virtual thread
    pinning — need Java 21+ to have any data; the tool degrades gracefully
    on older JDKs where an event type doesn't exist)
  - Python 3.10+

Output:
  - Recording metadata (JVM version/args, PID, duration, chunks)
  - CPU execution hot spots (method-level and full stack traces)
  - Memory allocation hotspots by type and allocation site, plus a
    TLAB-derived allocation-rate estimate (bytes/sec) that is far closer
    to the true total than the sampled view alone
  - GC / heap behavior timeline + GC pause-time breakdown by phase, with
    a young-vs-old-generation split
  - Safepoint time (best-effort; overlaps with GC pause time — see note
    in that section)
  - Class loading (loaded/unloaded counts) + Metaspace usage
  - Thread creation (counts, pool grouping) + virtual thread pinning
  - Lock contention (monitor enter waits, thread park waits)
  - JIT compilation time (total + top compiled methods + breakdown by
    tiered-compilation level)
  - Socket / file I/O activity (bytes + wait time)
  - CPU load timeline (JVM vs machine)
  - Thread idle time — real Thread.sleep() and Object.wait() events
    (NOT the old, nonexistent "profiler.WallClockSleeping" — see notes)
  - Uncaught/thrown exceptions, if that event was enabled for the recording
  - Side-by-side comparison (when two files are provided) for every section
    above, with deltas and ELIMINATED / NEW markers.


What It Analyzes

    ┌────────────────────────┬──────────────────────────────────────────┬────────────────────────────────────────────────────────────┐
    │ Section                │ Data Source                               │ What It Shows                                                │
    ├────────────────────────┼──────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
    │ Recording Metadata     │ `jfr summary` + jdk.JVMInformation        │ JVM version, PID, duration, chunks                           │
    │ CPU Hotspots           │ jdk.ExecutionSample                       │ Top hot leaf methods, thread distribution, top stacks       │
    │ Allocation Hotspots    │ jdk.ObjectAllocationSample                │ Top allocation types (sampled), top byte[] allocation sites │
    │ Allocation Rate        │ jdk.ObjectAllocationInNewTLAB/OutsideTLAB │ Near-total allocated bytes and bytes/sec (not sampled)      │
    │ GC/Heap Timeline       │ jdk.GCHeapSummary                         │ Heap growth over time, peak usage                            │
    │ GC Pause Times         │ jdk.GCPhasePause                          │ Pause count/total/avg/max, by phase, young-vs-old split      │
    │ Safepoints             │ jdk.SafepointBegin                        │ Total stop-the-world safepoint time (overlaps with GC)       │
    │ Class Loading          │ jdk.ClassLoadingStatistics                │ Loaded/unloaded class counts over time, final totals         │
    │ Metaspace              │ jdk.MetaspaceSummary                      │ Metaspace used/committed, peak usage                          │
    │ Thread Creation        │ jdk.ThreadStart / ThreadEnd               │ Threads started, grouped by pool/name prefix                 │
    │ Virtual Threads        │ jdk.VirtualThreadPinned/Start/End         │ Pinning events (carrier-thread starvation risk)               │
    │ Lock Contention        │ jdk.JavaMonitorEnter / ThreadPark         │ Top contended monitor classes, top parked classes             │
    │ JIT Compilation        │ jdk.Compilation                           │ Total compile time, top compiled methods, by-level breakdown │
    │ Socket / File I/O      │ jdk.SocketRead/Write, jdk.FileRead/Write  │ Bytes transferred + wait time, top hosts/paths                │
    │ CPU Load Timeline      │ jdk.CPULoad                               │ JVM user/system vs whole-machine CPU over time                │
    │ Thread Idle Time       │ jdk.ThreadSleep, jdk.JavaMonitorWait      │ Idle/wait time by thread, longest individual idle events      │
    │ Exceptions             │ jdk.JavaExceptionThrow                    │ Thrown-exception counts by class and throw site (if enabled) │
    │ Comparison Mode        │ Both files                                │ Delta tables for every section (ELIMINATED/NEW markers)       │
    └────────────────────────┴──────────────────────────────────────────┴────────────────────────────────────────────────────────────┘


Typical startup bottlenecks this tool reveals:

  CPU Hotspots:
    - ClassLoader.defineClass1    ->  Too many classes being loaded; use CDS or trim dependencies
    - Inflater.inflateBytes       ->  JAR decompression overhead; use CDS to bypass
    - Constructor.newInstance /
      Method.invoke               ->  Reflection-driven construction (DI/ORM); AOT processing helps
    - Classpath/annotation scanning->  Component-scanning framework overhead; build-time indexing helps

  Allocation Hotspots:
    - byte[] (Resource.getBytes)  ->  Class file bytes from JARs; use CDS
    - Framework annotation/reflection
      metadata objects            ->  Runtime DI/annotation processing; AOT processing helps
    - reflect/Field, reflect/Method-> Reflection metadata; AOT processing helps
    - ASM class-reader internals  ->  Bytecode parsing; AOT processing helps

  Other Sections:
    - High GC pause time          ->  Too many allocations; check allocation hotspots first
    - High safepoint time beyond
      GC pause time                ->  Non-GC safepoint operations (biased-lock revocation, deopt,
                                        JFR itself); usually minor, worth a look if surprisingly high
    - High class loading count    ->  Too many dependencies; trim classpath or use CDS
    - High Metaspace usage        ->  Same root cause as high class count
    - Lock contention on main     ->  Bottleneck in synchronized code; consider reducing lock scope
    - Virtual thread pinning      ->  synchronized blocks or native calls pinning carrier threads
    - High JIT compile time       ->  Code churn during startup; C1-only tiered compilation helps
    - High socket I/O             ->  Network calls during startup; defer or cache
    - High file I/O               ->  File scanning (JARs, classpath); use CDS or an indexer
    - Frequent exceptions         ->  Exception-driven control flow or misconfiguration; each throw
                                        costs stack-trace capture even when caught

Notes on correctness (read this if you're diffing against an older version
of this script):
  - Thread idle time now uses the real JFR events `jdk.ThreadSleep` and
    `jdk.JavaMonitorWait`. An earlier version of this tool referenced a
    `profiler.WallClockSleeping` event, which does not exist in standard
    JDK Flight Recorder — that was a bug, not a real data source. Fixed here.
  - Every event type used below has been checked against JFR metadata as
    published by the OpenJDK project and Oracle's own JFR troubleshooting
    docs. Field names occasionally drift between JDK versions (see
    `first_present()` / `dig()`), so this tool degrades gracefully — a
    missing or renamed field yields an empty section rather than a crash.
  - Safepoint time (new in this version) intentionally overlaps with GC
    pause time, since most safepoints exist to run a GC phase. Treat it as
    an upper bound on total stop-the-world time, not an additive cost on
    top of the GC numbers.
"""

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                         HELPER FUNCTIONS                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


def jfr_print_json(jfr_file: str, events: str) -> dict:
    """
    Invoke the JDK's `jfr` CLI to extract events as JSON.

    We use --json mode for events carrying numeric data (allocation weights,
    durations, heap sizes) because JSON preserves exact values.

    Parameters:
        jfr_file: Path to the .jfr recording.
        events:   Comma-separated JFR event type names.

    Returns:
        Parsed dict: {"recording": {"events": [...]}}
    """
    result = subprocess.run(
        ["jfr", "print", "--events", events, "--json", str(jfr_file)],
        capture_output=True, text=True, timeout=120,
    )
    output = result.stdout.strip()
    if not output:
        output = result.stderr.strip()
    return json.loads(output)


def jfr_print_text(jfr_file: str, events: str) -> str:
    """
    Invoke the JDK's `jfr` CLI to extract events as human-readable text.

    We use text mode for ExecutionSample events because the text format
    includes full stack traces in a compact, easy-to-regex-parse layout.
    """
    result = subprocess.run(
        ["jfr", "print", "--events", events, str(jfr_file)],
        capture_output=True, text=True, timeout=120,
    )
    return result.stdout.strip()


def jfr_summary_text(jfr_file: str) -> str:
    """
    Run `jfr summary <file>` to get recording-level metadata:
    version, chunks, start time, duration, event counts.
    """
    result = subprocess.run(
        ["jfr", "summary", str(jfr_file)],
        capture_output=True, text=True, timeout=120,
    )
    return result.stdout.strip()


def parse_duration_iso(dur) -> float:
    """
    Parse a JFR duration value into milliseconds.

    JFR's `--json` output has historically varied in how it renders
    durations depending on JDK version — sometimes an ISO-8601 string
    ("PT0.328702567S"), sometimes a plain "<number> <unit>" string
    ("100 ms", "0.045 s"), and occasionally a raw numeric value (assumed
    to be nanoseconds, matching RecordedEvent.getDuration()'s unit).
    This function tries all three so the tool doesn't silently report
    zero durations on a JDK version that formats things differently.
    """
    if dur is None or dur == 0:
        return 0.0
    if isinstance(dur, (int, float)):
        return float(dur) / 1_000_000  # nanos -> ms
    if isinstance(dur, str):
        s = dur.strip()
        m = re.match(r"PT([\d.]+)S", s)
        if m:
            return float(m.group(1)) * 1000  # ISO-8601 seconds -> ms
        m = re.match(r"([\d.]+)\s*(ns|us|ms|s)$", s)
        if m:
            value, unit = float(m.group(1)), m.group(2)
            return {"ns": value / 1_000_000, "us": value / 1000,
                    "ms": value, "s": value * 1000}[unit]
        try:
            return float(s) / 1_000_000  # bare numeric string, assume nanos
        except ValueError:
            return 0.0
    return 0.0


def dig(d: dict, *keys, default=None):
    """
    Walk a nested dict safely without KeyError on missing intermediate keys.

    Example: dig(v, 'method', 'type', 'name') safely navigates
    v['method']['type']['name'], returning None if any key is missing.
    This is critical for JFR JSON which has deeply nested optional fields
    that vary between JDK versions.
    """
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def first_present(d: dict, keys: list, default=0):
    """
    Return the value of the first key that exists in the dict.

    JFR field names sometimes change between JDK versions
    (e.g., 'loadedClassCount' vs 'classCount' vs 'numberOfLoadedClasses').
    This function tries each candidate and returns the first match.
    """
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def format_bytes(n: float) -> str:
    """Human-readable byte count with appropriate unit."""
    if abs(n) < 1024:
        return f"{n:,.0f} B"
    for unit in ["KB", "MB", "GB"]:
        n /= 1024.0
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}"
    return f"{n:,.1f} TB"


def pct_change(old: float, new: float) -> str:
    """
    Format a percentage change string.

    Returns:
        "+25.3%" for increases, "-50.0%" for decreases,
        "NEW" if old was zero and new is positive,
        "n/a" if both are zero.
    """
    if old == 0:
        return "NEW" if new > 0 else "n/a"
    return f"{(new - old) / old * 100:+.1f}%"


def bar(pct: float, width: int = 20) -> str:
    """Simple ASCII bar chart with bounds checking."""
    filled = int(abs(pct) / 100 * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def method_sig(frame_or_values: dict, *path) -> str:
    """
    Build a "Type.method" string from a nested method reference, tolerant
    of missing fields. `path` is the key path down to the object that has
    a `method` field (e.g. () for a top-level frame, or omitted entirely
    if `frame_or_values` already IS the frame).
    """
    node = dig(frame_or_values, *path) if path else frame_or_values
    return f"{dig(node, 'method', 'type', 'name', default='?')}.{dig(node, 'method', 'name', default='?')}"


def stack_signature(frames: list, depth: int = 4) -> str:
    """Join the first `depth` frames of a stack trace into a single string."""
    return " -> ".join(method_sig(f)[:80] for f in frames[:depth])


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                     JFR DATA MODEL (JfrAnalysis)                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# Declarative table of the JSON-mode event types we load. Keys become
# `self.<attr>` attributes holding a list of raw JFR event dicts. Centralizing
# this avoids ~20 near-identical, easy-to-typo try/except blocks — the single
# most common source of "this section is silently always empty" bugs in
# hand-rolled JFR tooling, and the reason `profiler.WallClockSleeping`
# (an event that never existed) went unnoticed for as long as it did.
JSON_EVENTS = {
    "alloc_samples":          "jdk.ObjectAllocationSample",
    "tlab_new_events":        "jdk.ObjectAllocationInNewTLAB",
    "tlab_outside_events":    "jdk.ObjectAllocationOutsideTLAB",
    "sleep_events":           "jdk.ThreadSleep",
    "wait_events":            "jdk.JavaMonitorWait",
    "gc_events":              "jdk.GCHeapSummary",
    "metaspace_events":       "jdk.MetaspaceSummary",
    "gc_pause_events":        "jdk.GCPhasePause",
    "safepoint_begin_events": "jdk.SafepointBegin",
    "class_loading_events":   "jdk.ClassLoadingStatistics",
    "thread_start_events":    "jdk.ThreadStart",
    "thread_end_events":      "jdk.ThreadEnd",
    "vthread_pinned_events":  "jdk.VirtualThreadPinned",
    "vthread_start_events":   "jdk.VirtualThreadStart",
    "vthread_end_events":     "jdk.VirtualThreadEnd",
    "monitor_enter_events":   "jdk.JavaMonitorEnter",
    "thread_park_events":     "jdk.ThreadPark",
    "compilation_events":     "jdk.Compilation",
    "socket_read_events":     "jdk.SocketRead",
    "socket_write_events":    "jdk.SocketWrite",
    "file_read_events":       "jdk.FileRead",
    "file_write_events":      "jdk.FileWrite",
    "cpu_load_events":        "jdk.CPULoad",
    "exception_events":       "jdk.JavaExceptionThrow",
}


class JfrAnalysis:
    """
    Parsed and queryable data from a single JFR recording.

    See JSON_EVENTS above for the full list of JSON-mode event types loaded.
    jdk.ExecutionSample is loaded separately in text mode (for full stack
    traces), and jdk.JVMInformation is loaded separately since it's a
    single metadata event rather than a series.
    """

    def __init__(self, jfr_file: str):
        self.file = jfr_file
        self.name = Path(jfr_file).stem

        self.cpu_samples: list[dict] = []
        self.jvm_info: dict = {}
        self.summary_text: str = ""

        # All JSON_EVENTS keys are initialized here so every attribute
        # exists (as an empty list) even if extraction fails or the event
        # type doesn't exist on this JDK version.
        for attr in JSON_EVENTS:
            setattr(self, attr, [])

        self._load()

    # ── Data Loading Helpers ──────────────────────────────────────────────

    def _try_json(self, event_type: str) -> list:
        """
        Safely load a JSON event type, returning [] on any error.

        Many JFR event types are conditionally enabled based on recording
        settings, or don't exist on a given JDK version. This helper
        prevents one missing/renamed event type from blocking the rest
        of the analysis.
        """
        try:
            data = jfr_print_json(self.file, event_type)
            return data.get("recording", {}).get("events", [])
        except Exception as e:
            print(f"  [WARN] {event_type}: {e}", file=sys.stderr)
            return []

    def _load(self):
        """
        Extract every event type listed in JSON_EVENTS, plus CPU samples
        (text mode) and JVM metadata. Each extraction is independent —
        failure or absence of one event type does not block the others.
        """
        print(f"[INFO] Loading {self.file} ...", file=sys.stderr)

        # ── Recording-level metadata ─────────────────────────────────────
        try:
            self.summary_text = jfr_summary_text(self.file)
        except Exception as e:
            print(f"  [WARN] summary: {e}", file=sys.stderr)

        info_events = self._try_json("jdk.JVMInformation")
        if info_events:
            self.jvm_info = info_events[0].get("values", {})

        # ── CPU execution samples (text mode for full stack traces) ───────
        try:
            text = jfr_print_text(self.file, "jdk.ExecutionSample")
            self._parse_cpu_text(text)
        except Exception as e:
            print(f"  [WARN] CPU samples: {e}", file=sys.stderr)

        # ── Everything else, driven by the declarative table ──────────────
        for attr, event_type in JSON_EVENTS.items():
            setattr(self, attr, self._try_json(event_type))

    # ── CPU Text Parser ──────────────────────────────────────────────────

    def _parse_cpu_text(self, text: str):
        """
        Parse the human-readable ExecutionSample output.

        Each block looks like:

            jdk.ExecutionSample {
              sampledThread = "DestroyJavaVM" (javaThreadId = 72)
              state = "STATE_RUNNABLE"
              stackTrace = [
                java.lang.ClassLoader.defineClass1(...) line: 0
                java.lang.ClassLoader.defineClass(...) line: 539
                ...
              ]
            }

        The first (index-0) frame is the leaf — the method actually running.
        Frames below are the call chain.
        """
        blocks = re.split(r"\njdk\.ExecutionSample \{", text)
        for block in blocks[1:]:
            sample: dict = {}
            tm = re.search(r'sampledThread\s*=\s*"([^"]+)"', block)
            sample["thread"] = tm.group(1) if tm else "unknown"
            sm = re.search(r'state\s*=\s*"([^"]+)"', block)
            sample["state"] = sm.group(1) if sm else "?"
            stack_sec = re.search(r"stackTrace\s*=\s*\[(.*?)\]", block, re.DOTALL)
            if stack_sec:
                sample["frames"] = [
                    f.strip()
                    for f in stack_sec.group(1).strip().split("\n")
                    if f.strip()
                ]
            else:
                sample["frames"] = []
            self.cpu_samples.append(sample)

    # ── Metadata Accessors ───────────────────────────────────────────────

    def recording_duration_s(self) -> float:
        """Parse duration from the jfr summary output."""
        m = re.search(r"Duration:\s*([\d.]+)\s*s", self.summary_text)
        return float(m.group(1)) if m else 0.0

    def recording_start(self) -> str:
        m = re.search(r"Start:\s*(.+)", self.summary_text)
        return m.group(1).strip() if m else "unknown"

    def recording_chunks(self) -> str:
        m = re.search(r"Chunks:\s*(\d+)", self.summary_text)
        return m.group(1) if m else "?"

    def jvm_version(self) -> str:
        return self.jvm_info.get("jvmVersion", "unknown").split("\n")[0]

    def jvm_arguments(self) -> str:
        return self.jvm_info.get("jvmArguments", "n/a")

    def java_arguments(self) -> str:
        return self.jvm_info.get("javaArguments", "n/a")

    def pid(self) -> str:
        return str(self.jvm_info.get("pid", "n/a"))

    # ── CPU Accessors ────────────────────────────────────────────────────

    def cpu_method_counts(self) -> Counter:
        """
        Leaf (top-of-stack) method sample counts.
        The leaf frame is the method actively running when the sample fired.
        """
        c: Counter[str] = Counter()
        for s in self.cpu_samples:
            if s["frames"]:
                c[s["frames"][0]] += 1
        return c

    def cpu_thread_counts(self) -> Counter:
        """Thread distribution of CPU samples."""
        c: Counter[str] = Counter()
        for s in self.cpu_samples:
            c[s["thread"]] += 1
        return c

    def cpu_stack_sigs(self, depth: int = 5) -> Counter:
        """
        Full stack signatures showing the call chain.
        The leaf tells WHAT is hot; the stack tells WHY.
        """
        c: Counter[str] = Counter()
        for s in self.cpu_samples:
            sig = " -> ".join(f[:90] for f in s["frames"][:depth])
            c[sig] += 1
        return c

    @property
    def cpu_sample_count(self) -> int:
        return len(self.cpu_samples)

    # ── Allocation Accessors (sampled) ───────────────────────────────────

    def alloc_by_class(self) -> Counter:
        """
        Sum sampled allocation weight (bytes) by object class name.

        This is JFR's *statistical sample* of allocations (jdk.ObjectAllocationSample),
        useful for finding allocation SITES, but not a precise total — for
        that, see `tlab_total_bytes()` / `allocation_rate_bytes_per_sec()`.
        """
        c: Counter[str] = Counter()
        for e in self.alloc_samples:
            v = e["values"]
            cls_name = dig(v, "objectClass", "name", default="unknown")
            c[cls_name] += v.get("weight", 0) or 0
        return c

    def alloc_stack_sigs(self, class_filter: str | None = None, depth: int = 4) -> Counter:
        """
        Allocation stack signatures, optionally filtered by class name.

        Pass class_filter="[B" to find WHERE byte arrays are allocated from.
        """
        c: Counter[str] = Counter()
        for e in self.alloc_samples:
            v = e["values"]
            cls_name = dig(v, "objectClass", "name", default="unknown")
            if class_filter and class_filter not in cls_name:
                continue
            weight = v.get("weight", 0) or 0
            frames = dig(v, "stackTrace", "frames", default=[])
            if frames:
                c[stack_signature(frames, depth)] += weight
        return c

    @property
    def total_alloc_bytes(self) -> int:
        return sum(self.alloc_by_class().values())

    @property
    def alloc_sample_count(self) -> int:
        return len(self.alloc_samples)

    # ── Allocation Accessors (TLAB-derived — near-exhaustive, not sampled) ─

    def tlab_by_class(self) -> Counter:
        """
        Sum near-total allocated bytes by class, derived from TLAB events
        rather than statistical sampling.

        `jdk.ObjectAllocationInNewTLAB` fires once per thread-local
        allocation buffer refill and reports `tlabSize` — a close proxy
        for bytes consumed by that thread since its previous refill.
        `jdk.ObjectAllocationOutsideTLAB` fires for large objects
        allocated directly (bypassing TLABs) and reports `allocationSize`
        exactly. Summing both gives a far more complete picture of total
        allocation than the sampled `jdk.ObjectAllocationSample` events —
        this is the same technique JDK Mission Control uses for its
        "Allocations" view.
        """
        c: Counter[str] = Counter()
        for e in self.tlab_new_events:
            v = e["values"]
            cls_name = dig(v, "objectClass", "name", default="unknown")
            c[cls_name] += v.get("tlabSize", 0) or 0
        for e in self.tlab_outside_events:
            v = e["values"]
            cls_name = dig(v, "objectClass", "name", default="unknown")
            c[cls_name] += v.get("allocationSize", 0) or 0
        return c

    @property
    def tlab_total_bytes(self) -> int:
        return sum(self.tlab_by_class().values())

    @property
    def tlab_event_count(self) -> int:
        return len(self.tlab_new_events) + len(self.tlab_outside_events)

    def allocation_rate_bytes_per_sec(self) -> float:
        """
        Estimated sustained allocation rate over the recording window,
        derived from TLAB events (see `tlab_by_class`), not the sampled
        allocation profile. Zero if the recording has no duration or no
        TLAB events (e.g., they weren't enabled).
        """
        dur = self.recording_duration_s()
        return self.tlab_total_bytes / dur if dur > 0 else 0.0

    # ── Idle Time Accessors (real events: ThreadSleep + JavaMonitorWait) ──
    #
    # NOTE: an earlier version of this tool used a nonexistent
    # "profiler.WallClockSleeping" event for this section. There is no
    # such event in standard JFR. The real coverage for "a thread was
    # voluntarily idle" comes from jdk.ThreadSleep (explicit Thread.sleep),
    # jdk.JavaMonitorWait (Object.wait()), and jdk.ThreadPark (already
    # used separately in the Lock Contention section for
    # java.util.concurrent waits).

    def idle_by_thread(self) -> Counter:
        """Total idle duration (ms) by thread name, across sleep + wait events."""
        c: Counter[str] = Counter()
        for e in self.sleep_events + self.wait_events:
            v = e["values"]
            t = dig(v, "eventThread", "javaName", default="?")
            c[t] += parse_duration_iso(v.get("duration", 0))
        return c

    def idle_longest(self, n: int = 15) -> list[tuple[float, str, str, str]]:
        """
        Top N longest individual idle events (sleep or monitor-wait),
        with thread, top frame, and which kind of idle it was.
        """
        tagged = [("SLEEP", e) for e in self.sleep_events] + \
                 [("WAIT", e) for e in self.wait_events]
        tagged.sort(key=lambda te: parse_duration_iso(te[1]["values"].get("duration", 0)), reverse=True)
        result: list[tuple[float, str, str, str]] = []
        for kind, e in tagged[:n]:
            v = e["values"]
            dur_ms = parse_duration_iso(v.get("duration", 0))
            frames = dig(v, "stackTrace", "frames", default=[])
            top_frame = method_sig(frames[0]) if frames else "unknown"
            thread = dig(v, "eventThread", "javaName", default="?")
            result.append((dur_ms, thread, top_frame, kind))
        return result

    @property
    def total_idle_ms(self) -> float:
        return sum(self.idle_by_thread().values())

    # ── GC Accessors ─────────────────────────────────────────────────────

    def gc_heap_series(self) -> list[tuple[str, float]]:
        """Heap usage time series: [(timestamp, heap_used_mb), ...]."""
        return [
            (e["values"].get("startTime", "")[:19],
             e["values"].get("heapUsed", 0) / 1024 / 1024)
            for e in self.gc_events
        ]

    def gc_pause_stats(self) -> dict:
        """
        Aggregate GC pause statistics.

        Returns dict with keys: count, total_ms, avg_ms, max_ms.
        GC pause time directly impacts application responsiveness.
        High total pause time indicates GC is struggling to keep up
        with allocation pressure.
        """
        durations = [parse_duration_iso(e["values"].get("duration", 0)) for e in self.gc_pause_events]
        if not durations:
            return {"count": 0, "total_ms": 0.0, "avg_ms": 0.0, "max_ms": 0.0}
        return {
            "count": len(durations),
            "total_ms": sum(durations),
            "avg_ms": sum(durations) / len(durations),
            "max_ms": max(durations),
        }

    def gc_pause_by_phase(self) -> Counter:
        """
        Break down GC pause time by phase name.

        Different phases (e.g., "GC Pause Young", "GC Pause Full")
        indicate which type of collection is consuming time. Phase
        naming is collector-specific — G1's names won't match ZGC's
        or Shenandoah's, so don't assume a fixed set of names.
        """
        c: Counter[str] = Counter()
        for e in self.gc_pause_events:
            v = e["values"]
            name = v.get("name", "unknown")
            c[name] += parse_duration_iso(v.get("duration", 0))
        return c

    def gc_pause_generation_split(self) -> tuple[float, float, float]:
        """
        Heuristic young/old/other split of GC pause time, based on
        substring matching against phase names. This is a best-effort
        classification — it works for G1's conventional phase naming
        ("... Young ...", "... Full ...") but may bucket everything as
        "other" on collectors with different naming (ZGC, Shenandoah).
        Returns (young_ms, old_ms, other_ms).
        """
        young_ms = old_ms = other_ms = 0.0
        for name, ms in self.gc_pause_by_phase().items():
            lname = name.lower()
            if "young" in lname:
                young_ms += ms
            elif "full" in lname or "old" in lname or "major" in lname:
                old_ms += ms
            else:
                other_ms += ms
        return young_ms, old_ms, other_ms

    # ── Safepoint Accessors ──────────────────────────────────────────────

    @property
    def safepoint_total_ms(self) -> float:
        """
        Best-effort total safepoint (stop-the-world) time, from
        jdk.SafepointBegin durations. Most safepoints exist to run a GC
        phase, so this figure OVERLAPS with GC pause time above rather
        than adding to it — use it as a sanity-check upper bound on total
        stop-the-world time, not a separate cost to sum with GC pauses.
        """
        return sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.safepoint_begin_events)

    # ── Metaspace Accessors ──────────────────────────────────────────────

    def metaspace_series(self) -> list[tuple[str, float, float]]:
        """Time series of (timestamp, used_bytes, committed_bytes)."""
        out = []
        for e in self.metaspace_events:
            v = e["values"]
            used = dig(v, "metaspace", "used", default=0)
            committed = dig(v, "metaspace", "committed", default=0)
            out.append((v.get("startTime", "")[:19], used, committed))
        return out

    def metaspace_peak(self) -> tuple[float, float]:
        """(peak_used_bytes, peak_committed_bytes), or (0, 0) if unavailable."""
        series = self.metaspace_series()
        if not series:
            return (0.0, 0.0)
        return (max(s[1] for s in series), max(s[2] for s in series))

    # ── Class Loading Accessors ──────────────────────────────────────────

    def class_loading_final(self) -> tuple[int, int]:
        """
        Return (loaded, unloaded) from the last statistics event.

        The ClassLoadingStatistics event is cumulative — the last event
        tells us the total number of classes loaded during the recording.

        Uses first_present() to handle JDK field-name drift.
        """
        if not self.class_loading_events:
            return (0, 0)
        v = self.class_loading_events[-1]["values"]
        loaded = first_present(v, ["loadedClassCount", "classCount", "numberOfLoadedClasses"])
        unloaded = first_present(v, ["unloadedClassCount", "numberOfUnloadedClasses"])
        return (loaded, unloaded)

    def class_loading_series(self) -> list[tuple[str, int]]:
        """Time series of cumulative loaded class counts."""
        out = []
        for e in self.class_loading_events:
            v = e["values"]
            loaded = first_present(v, ["loadedClassCount", "classCount", "numberOfLoadedClasses"])
            out.append((v.get("startTime", "")[:19], loaded))
        return out

    # ── Thread Creation Accessors ────────────────────────────────────────

    @property
    def thread_start_count(self) -> int:
        return len(self.thread_start_events)

    @property
    def thread_end_count(self) -> int:
        return len(self.thread_end_events)

    def thread_pool_breakdown(self) -> Counter:
        """
        Group started threads by normalized name prefix.

        Normalization: strips trailing digits/hex-ids so pool threads
        (e.g., "http-nio-8080-exec-1", "http-nio-8080-exec-2") group
        together under "http-nio-8080-exec". Works for most web-server,
        connection-pool, and scheduler naming conventions regardless of
        which specific libraries are in use.
        """
        c: Counter[str] = Counter()
        for e in self.thread_start_events:
            v = e["values"]
            name = dig(v, "thread", "javaName", default="unknown")
            norm = re.sub(r"[-#]?\d+$", "", name).strip() or name
            c[norm] += 1
        return c

    # ── Virtual Thread Accessors ─────────────────────────────────────────

    @property
    def vthread_pinned_count(self) -> int:
        return len(self.vthread_pinned_events)

    @property
    def vthread_pinned_total_ms(self) -> float:
        return sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.vthread_pinned_events)

    def vthread_pinned_top(self, n: int = 15) -> list[tuple[str, int, float]]:
        """Top N pinning call sites by event count, with total pinned time."""
        counts: Counter[str] = Counter()
        durations: Counter[str] = Counter()
        for e in self.vthread_pinned_events:
            v = e["values"]
            frames = dig(v, "stackTrace", "frames", default=[])
            sig = stack_signature(frames, depth=4) if frames else "(no stack trace)"
            counts[sig] += 1
            durations[sig] += parse_duration_iso(v.get("duration", 0))
        return [(sig, counts[sig], durations[sig]) for sig, _ in counts.most_common(n)]

    @property
    def vthread_start_count(self) -> int:
        """
        Count of jdk.VirtualThreadStart events. This event is DISABLED by
        default even under the `profile` settings template — a zero here
        commonly just means the event wasn't enabled, not that no virtual
        threads were created. jdk.VirtualThreadPinned, by contrast, IS
        enabled by default on JDK 21+, so that's the more reliable signal.
        """
        return len(self.vthread_start_events)

    # ── Lock Contention Accessors ────────────────────────────────────────

    def monitor_contention_top(self, n: int = 20) -> list[tuple[str, float, int]]:
        """
        Top N contended monitor (synchronized) classes by total wait time.

        Returns list of (class_name, total_wait_ms, event_count).
        High wait time on a class means multiple threads are contending
        for a synchronized block/method on that class. Note that JFR only
        records monitor-contention events above a threshold (commonly
        20ms by default) — shorter contention won't appear unless that
        threshold was lowered when the recording was started.
        """
        c: Counter[str] = Counter()
        counts: Counter[str] = Counter()
        for e in self.monitor_enter_events:
            v = e["values"]
            cls = dig(v, "monitorClass", "name", default="unknown")
            dur = parse_duration_iso(v.get("duration", 0))
            c[cls] += dur
            counts[cls] += 1
        return [(cls, ms, counts[cls]) for cls, ms in c.most_common(n)]

    @property
    def monitor_contention_total_ms(self) -> float:
        return sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.monitor_enter_events)

    def thread_park_top(self, n: int = 20) -> list[tuple[str, float, int]]:
        """
        Top N parked classes by total park time.

        Thread parks are java.util.concurrent lock waits (e.g.,
        ReentrantLock, CountDownLatch, park/unpark). A park event by
        itself is not necessarily a problem — it's the normal mechanism
        behind idle worker threads waiting for work — so weigh this
        against what's actually calling park() (the stack trace) rather
        than the raw total.
        """
        c: Counter[str] = Counter()
        counts: Counter[str] = Counter()
        for e in self.thread_park_events:
            v = e["values"]
            cls = dig(v, "parkedClass", "name", default="unknown")
            dur = parse_duration_iso(v.get("duration", 0))
            c[cls] += dur
            counts[cls] += 1
        return [(cls, ms, counts[cls]) for cls, ms in c.most_common(n)]

    @property
    def thread_park_total_ms(self) -> float:
        return sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.thread_park_events)

    # ── JIT Compilation Accessors ────────────────────────────────────────

    @property
    def compilation_total_ms(self) -> float:
        """Total time spent in JIT compilation. High values during startup
        indicate the JIT is working hard to compile hot methods."""
        return sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.compilation_events)

    @property
    def compilation_count(self) -> int:
        return len(self.compilation_events)

    def compilation_top_methods(self, n: int = 20) -> list[tuple[float, str, str]]:
        """
        Top N methods by compilation time.

        Returns list of (time_ms, method_signature, compile_level).
        Compile level: 0=interpreter, 1-3=C1 (increasing profiling),
        4=C2 (fully optimizing, most expensive to produce).
        """
        rows = []
        for e in self.compilation_events:
            v = e["values"]
            dur = parse_duration_iso(v.get("duration", 0))
            method = method_sig(v)
            level = v.get("compileLevel", "?")
            rows.append((dur, method, level))
        rows.sort(key=lambda r: r[0], reverse=True)
        return rows[:n]

    def compilation_by_level(self) -> tuple[Counter, Counter]:
        """
        Compilation count and total time, grouped by tiered-compilation
        level. Returns (count_by_level, time_ms_by_level). A recording
        with no level-4 (C2) activity means the process never reached
        full optimization for any method — expected for very short-lived
        processes, worth investigating for long-running ones.
        """
        counts: Counter = Counter()
        times: Counter = Counter()
        for e in self.compilation_events:
            v = e["values"]
            level = v.get("compileLevel", "?")
            counts[level] += 1
            times[level] += parse_duration_iso(v.get("duration", 0))
        return counts, times

    # ── Exception Accessors ──────────────────────────────────────────────

    def exception_by_class(self, n: int = 25) -> list[tuple[str, int]]:
        """
        Top N thrown-exception classes by count. Requires
        jdk.JavaExceptionThrow, which is NOT enabled under the default
        `profile` settings template on most JDK versions — an empty
        result here more often means "not recorded" than "no exceptions".
        """
        c: Counter[str] = Counter()
        for e in self.exception_events:
            v = e["values"]
            cls = dig(v, "thrownClass", "name", default="unknown")
            c[cls] += 1
        return c.most_common(n)

    def exception_top_stacks(self, n: int = 15) -> list[tuple[str, int]]:
        """Top N throw-site stack signatures by count."""
        c: Counter[str] = Counter()
        for e in self.exception_events:
            v = e["values"]
            frames = dig(v, "stackTrace", "frames", default=[])
            if frames:
                c[stack_signature(frames, depth=4)] += 1
        return c.most_common(n)

    @property
    def exception_count(self) -> int:
        return len(self.exception_events)

    # ── I/O Accessors ────────────────────────────────────────────────────

    def io_socket_summary(self) -> dict:
        """Aggregate socket I/O: count, bytes, wait time for reads/writes."""
        read_bytes = sum(e["values"].get("bytesRead", 0) or 0 for e in self.socket_read_events)
        write_bytes = sum(e["values"].get("bytesWritten", 0) or 0 for e in self.socket_write_events)
        read_ms = sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.socket_read_events)
        write_ms = sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.socket_write_events)
        return {
            "read_count": len(self.socket_read_events), "read_bytes": read_bytes, "read_ms": read_ms,
            "write_count": len(self.socket_write_events), "write_bytes": write_bytes, "write_ms": write_ms,
        }

    def io_socket_top_hosts(self, n: int = 15) -> list[tuple[str, float]]:
        """Top hosts by socket I/O wait time."""
        c: Counter[str] = Counter()
        for e in self.socket_read_events + self.socket_write_events:
            v = e["values"]
            c[v.get("host", "?")] += parse_duration_iso(v.get("duration", 0))
        return c.most_common(n)

    def io_file_summary(self) -> dict:
        """Aggregate file I/O: count, bytes, wait time for reads/writes."""
        read_bytes = sum(e["values"].get("bytesRead", 0) or 0 for e in self.file_read_events)
        write_bytes = sum(e["values"].get("bytesWritten", 0) or 0 for e in self.file_write_events)
        read_ms = sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.file_read_events)
        write_ms = sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.file_write_events)
        return {
            "read_count": len(self.file_read_events), "read_bytes": read_bytes, "read_ms": read_ms,
            "write_count": len(self.file_write_events), "write_bytes": write_bytes, "write_ms": write_ms,
        }

    def io_file_top_paths(self, n: int = 15) -> list[tuple[str, float]]:
        """Top file paths by I/O wait time."""
        c: Counter[str] = Counter()
        for e in self.file_read_events + self.file_write_events:
            v = e["values"]
            c[v.get("path", "?")] += parse_duration_iso(v.get("duration", 0))
        return c.most_common(n)

    # ── CPU Load Accessors ───────────────────────────────────────────────

    def cpu_load_series(self) -> list[tuple[str, float, float, float]]:
        """
        Time series of CPU load: [(timestamp, jvm_user%, jvm_system%, machine_total%), ...].

        JVM user% = CPU spent in JVM user-mode code.
        JVM system% = CPU spent in kernel on behalf of JVM (e.g., I/O syscalls).
        Machine total% = total CPU utilization on the host.
        """
        out = []
        for e in self.cpu_load_events:
            v = e["values"]
            out.append((
                v.get("startTime", "")[:19],
                (v.get("jvmUser", 0) or 0) * 100,
                (v.get("jvmSystem", 0) or 0) * 100,
                (v.get("machineTotal", 0) or 0) * 100,
            ))
        return out

    def cpu_load_avg(self) -> tuple[float, float, float]:
        """Average (jvm_user%, jvm_system%, machine_total%) over the recording."""
        series = self.cpu_load_series()
        if not series:
            return (0.0, 0.0, 0.0)
        n = len(series)
        return (
            sum(s[1] for s in series) / n,
            sum(s[2] for s in series) / n,
            sum(s[3] for s in series) / n,
        )


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                         REPORT RENDERING                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

SECTION_WIDTH = 95

MARKDOWN = False  # set by --markdown / -m flag


def print_header(title: str):
    """Print a centered, double-lined section header."""
    if MARKDOWN:
        print(f"\n## {title}\n")
    else:
        print()
        print("=" * SECTION_WIDTH)
        print(f"{title:^{SECTION_WIDTH}}")
        print("=" * SECTION_WIDTH)


def print_subheader(title: str):
    """Print a subsection header with underline."""
    if MARKDOWN:
        print(f"\n### {title}\n")
    else:
        print(f"\n{title}")
        print("-" * min(SECTION_WIDTH, len(title)))


def print_note(text: str):
    """Print an informational note about metric significance under a section header."""
    if MARKDOWN:
        print(f"> 💡 {text}\n")
    else:
        print(f"  💡 {text}")


# ── Table helpers (markdown-aware) ─────────────────────────────────────

def _tbl_hdr(cols: str):
    """Print a table header row. In markdown mode wraps with |."""
    if MARKDOWN:
        inner = cols.strip()
        print("| " + re.sub(r" {2,}", " | ", inner) + " |")
    else:
        print(f"  {cols}")


def _tbl_sep(widths: list[int]):
    """Print a table separator row."""
    if MARKDOWN:
        print("|" + "|".join("-" * w for w in widths) + "|")
    else:
        print("  " + " ".join("-" * w for w in widths))


def _tbl_row(cols: str):
    """Print a table data row."""
    if MARKDOWN:
        inner = cols.strip()
        print("| " + re.sub(r" {2,}", " | ", inner) + " |")
    else:
        print(f"  {cols}")


def _tbl_title(text: str, width: int):
    """Print a centered table title. Bold in markdown, centered in text mode."""
    if MARKDOWN:
        print(f"\n**{text}**\n")
    else:
        print(f"\n  {text:^{width}}")


def report_single(analysis: JfrAnalysis):
    """
    Print a complete analysis report for a single JFR file.

    Report sections (in order):
    1.  Recording Metadata
    2.  CPU Execution Hotspots
    3.  Memory Allocation Hotspots (sampled) + Allocation Rate (TLAB-derived)
    4.  GC / Heap Timeline
    5.  GC Pause Times (+ young/old generation split)
    6.  Safepoints
    7.  Class Loading + Metaspace
    8.  Thread Creation
    9.  Virtual Threads (pinning)
    10. Lock Contention
    11. JIT Compilation (+ by-level breakdown)
    12. Socket / File I/O
    13. CPU Load Timeline
    14. Thread Idle Time (sleep + monitor wait)
    15. Exceptions
    """
    print_header(f"JFR ANALYSIS: {analysis.name}")

    # ── Section 1: Recording Metadata ────────────────────────────────────
    print_subheader("Recording Metadata")
    print(f"  File:            {analysis.file}")
    print(f"  Start:           {analysis.recording_start()}")
    print(f"  Duration:        {analysis.recording_duration_s():.3f} s")
    print(f"  Chunks:          {analysis.recording_chunks()}")
    print(f"  JVM version:     {analysis.jvm_version()}")
    print(f"  PID:             {analysis.pid()}")
    print(f"  JVM arguments:   {analysis.jvm_arguments()}")
    print(f"  Java arguments:  {analysis.java_arguments()}")

    # ── Section 2: CPU Hotspots ──────────────────────────────────────────
    print_header("CPU EXECUTION HOTSPOTS")
    print_note("Hot leaf methods show where CPU time is actually spent. High concentration in few methods -> clear optimization target. Well-distributed samples -> healthy throughput with no single bottleneck. ClassLoader.defineClass / Inflater.inflateBytes -> class loading / JAR decompression overhead (use CDS). Classpath/annotation scanning -> component-scanning framework overhead (build-time indexing helps). Sample counts under ~10-20 in a large recording are statistically noisy — don't over-interpret them.")
    methods = analysis.cpu_method_counts()
    total = sum(methods.values()) or 1
    print(f"\n  Total samples: {int(total)}")
    _tbl_title("Top 30 Hot Leaf Methods", 80)
    _tbl_hdr(f"  {'Method':<70} {'Count':>7} {'Pct':>7}")
    _tbl_sep([70, 7, 7])
    for method, count in methods.most_common(30):
        _tbl_row(f"  {method[:68]:<68} {count:>7d} {count/total*100:>6.1f}%")

    threads = analysis.cpu_thread_counts()
    _tbl_title("Thread Distribution", 80)
    _tbl_hdr(f"  {'Thread':<50} {'Count':>7} {'Pct':>7}")
    _tbl_sep([50, 7, 7])
    for t, c in threads.most_common(15):
        _tbl_row(f"  {t[:48]:<48} {c:>7d} {c/total*100:>6.1f}%")

    print_header("TOP CPU STACK SIGNATURES (top 5 frames)")
    print_note("Full call chains showing WHY a leaf method is hot — the leaf tells WHAT is burning CPU, the stack tells WHY it's being called. Deep framework call chains -> framework overhead dominates; shallow chains -> application logic is the main cost.")
    sigs = analysis.cpu_stack_sigs(depth=5)
    for sig, count in sigs.most_common(20):
        print(f"\n  [{count}x, {count/total*100:.1f}%]")
        for line in sig.split(" -> "):
            print(f"    {line}")

    # ── Section 3: Allocation Hotspots ───────────────────────────────────
    print_header("MEMORY ALLOCATION HOTSPOTS (sampled)")
    print_note("Allocation rate directly drives GC frequency — every allocated byte must eventually be collected. This section is a STATISTICAL SAMPLE (jdk.ObjectAllocationSample), good for finding hot allocation sites; see 'Allocation Rate' below for a near-total, non-sampled figure. Framework annotation/reflection objects -> DI/bytecode processing overhead. Domain objects -> business logic.")
    alloc = analysis.alloc_by_class()
    total_alloc = sum(alloc.values()) or 1
    print(f"\n  Total sampled allocation: {format_bytes(total_alloc)}")
    print(f"  Sample count: {analysis.alloc_sample_count}")

    _tbl_title("Top 40 Allocation Types (sampled)", 80)
    _tbl_hdr(f"  {'Type':<55} {'Bytes':>14} {'Pct':>7}")
    _tbl_sep([55, 14, 7])
    for cls, w in alloc.most_common(40):
        _tbl_row(f"  {cls[:53]:<53} {w:>14,d} {w/total_alloc*100:>6.1f}%")

    print_header("TOP byte[] ALLOCATION SITES")
    print_note("byte[] is typically the #1 allocation type in JVM applications. Allocation sites reveal the root cause: Resource.getBytes / ClassLoader.defineClass -> class loading from JARs (use CDS); StreamDecoder / SocketChannel -> I/O; ByteArrayOutputStream -> serialization/buffering.")
    byte_stacks = analysis.alloc_stack_sigs(class_filter="[B", depth=4)
    total_byte = sum(byte_stacks.values()) or 1
    print(f"\n  Total byte[] (sampled): {format_bytes(total_byte)}")
    for sig, w in byte_stacks.most_common(20):
        _tbl_row(f"\n  {w:>12,d} ({w/total_byte*100:.1f}%)")
        for line in sig.split(" -> "):
            print(f"    {line}")

    print_header("ALLOCATION RATE (TLAB-derived, not sampled)")
    print_note("Derived from jdk.ObjectAllocationInNewTLAB + jdk.ObjectAllocationOutsideTLAB, which fire on essentially every allocation event rather than a statistical sample — this is a much closer approximation of TOTAL bytes allocated than the sampled section above. Remember: allocation rate measures what's CREATED, not what's RETAINED — a high rate with a flat, modest heap just means fast churn of short-lived objects, which is normal.")
    tlab_total = analysis.tlab_total_bytes
    rate = analysis.allocation_rate_bytes_per_sec()
    print(f"\n  Total allocated (TLAB-derived): {format_bytes(tlab_total)}")
    print(f"  TLAB/large-object events: {analysis.tlab_event_count:,}")
    if rate > 0:
        print(f"  Estimated allocation rate: {format_bytes(rate)}/s")
    else:
        print("  Estimated allocation rate: n/a (no TLAB events — this event type may not be enabled)")
    tlab_by_cls = analysis.tlab_by_class()
    if tlab_by_cls:
        _tbl_title("Top 20 Types by TLAB-derived Bytes", 80)
        _tbl_hdr(f"  {'Type':<55} {'Bytes':>14} {'Pct':>7}")
        _tbl_sep([55, 14, 7])
        tlab_grand_total = sum(tlab_by_cls.values()) or 1
        for cls, w in tlab_by_cls.most_common(20):
            _tbl_row(f"  {cls[:53]:<53} {w:>14,d} {w/tlab_grand_total*100:>6.1f}%")

    # ── Section 4: GC / Heap Timeline ────────────────────────────────────
    print_header("GC / HEAP TIMELINE")
    print_note("Rapid heap growth -> high allocation pressure. High peak usage -> memory-hungry workload or potential leak. A flat heap curve after initial startup ramp-up is healthy.")
    heap = analysis.gc_heap_series()
    if heap:
        peaks = [h[1] for h in heap]
        print(f"\n  Events: {len(heap)}")
        print(f"  Heap range: {min(peaks):.1f} MB -> {max(peaks):.1f} MB (peak)")
        _tbl_hdr(f"\n  {'Timestamp':<22} {'Heap':>10}")
        _tbl_sep([22, 10])
        for ts, mb in heap:
            _tbl_row(f"  {ts:<22} {mb:>8.1f} MB")
    else:
        print("\n  No GCHeapSummary events found.")

    # ── Section 5: GC Pause Times ────────────────────────────────────────
    print_header("GC PAUSE TIMES")
    print_note("Stop-the-world pauses directly impact application responsiveness. High total pause (rough guide: >5% of recording) -> GC is struggling with allocation rate. Max pause well above your latency budget -> potential user-visible spike. Old-gen/full pauses are most concerning. Phase naming is collector-specific (G1 vs ZGC vs Shenandoah) — the young/old split below is a heuristic, not exact for every collector.")
    stats = analysis.gc_pause_stats()
    print(f"\n  Pause count: {stats['count']}")
    print(f"  Total pause time: {stats['total_ms']:,.1f} ms")
    print(f"  Avg pause: {stats['avg_ms']:,.2f} ms   Max pause: {stats['max_ms']:,.2f} ms")
    if analysis.recording_duration_s() > 0:
        pct_run = stats['total_ms'] / 1000 / analysis.recording_duration_s() * 100
        print(f"  Pause time as % of recording: {pct_run:.2f}%")
    young_ms, old_ms, other_ms = analysis.gc_pause_generation_split()
    print(f"  Heuristic split — young: {young_ms:,.1f} ms   old/full: {old_ms:,.1f} ms   other/unclassified: {other_ms:,.1f} ms")
    by_phase = analysis.gc_pause_by_phase()
    if by_phase:
        _tbl_title("By Phase", 60)
        _tbl_hdr(f"  {'Phase':<40} {'Total (ms)':>15}")
        _tbl_sep([40, 15])
        for phase, ms in by_phase.most_common(15):
            _tbl_row(f"  {phase[:38]:<38} {ms:>15,.1f}")

    # ── Section 6: Safepoints ────────────────────────────────────────────
    print_header("SAFEPOINTS")
    print_note("Best-effort total stop-the-world safepoint time (jdk.SafepointBegin). Most safepoints exist to run a GC phase, so this OVERLAPS with the GC pause numbers above — treat it as an upper bound on total stop-the-world time, not an additive cost. A large gap between this number and GC pause time suggests non-GC safepoint work (biased-lock revocation, deoptimization, thread dumps, JFR's own periodic checkpoints).")
    sp_total = analysis.safepoint_total_ms
    gc_total = stats['total_ms']
    print(f"\n  Safepoint events: {len(analysis.safepoint_begin_events):,}")
    print(f"  Total safepoint time: {sp_total:,.1f} ms")
    if sp_total > 0:
        non_gc = max(0.0, sp_total - gc_total)
        print(f"  Of which not attributable to GC pauses (rough estimate): {non_gc:,.1f} ms")

    # ── Section 7: Class Loading ─────────────────────────────────────────
    print_header("CLASS LOADING")
    print_note("Higher class count -> slower startup, more metadata memory in Metaspace. Reduce with CDS (Class Data Sharing), build-time/AOT processing, or trimming unused dependencies. A growing unloaded-class count over a long-running process may indicate a classloader leak.")
    loaded, unloaded = analysis.class_loading_final()
    print(f"\n  Classes loaded (final):   {loaded:,}")
    print(f"  Classes unloaded (final): {unloaded:,}")
    peak_used, peak_committed = analysis.metaspace_peak()
    if peak_committed > 0:
        print(f"  Metaspace peak used:      {format_bytes(peak_used)}")
        print(f"  Metaspace peak committed: {format_bytes(peak_committed)}")
    series = analysis.class_loading_series()
    if series:
        _tbl_hdr(f"\n  {'Timestamp':<22} {'Loaded classes':>16}")
        _tbl_sep([22, 16])
        for ts, n in series[-15:]:
            _tbl_row(f"  {ts:<22} {n:>16,d}")

    # ── Section 8: Thread Creation ───────────────────────────────────────
    print_header("THREAD CREATION")
    print_note("Excessive thread creation -> overhead from stack allocation and context switching. Pools grouped by prefix show which subsystems are active. A few dozen threads is normal for a typical server app; hundreds may indicate a leak or misconfiguration. If your app uses virtual threads, raw counts stop being meaningful on their own — see the Virtual Threads section below.")
    print(f"\n  Threads started: {analysis.thread_start_count:,}")
    print(f"  Threads ended:   {analysis.thread_end_count:,}")
    pools = analysis.thread_pool_breakdown()
    if pools:
        _tbl_title("Grouped by pool / name prefix", 70)
        _tbl_hdr(f"  {'Pool / prefix':<50} {'Started':>10}")
        _tbl_sep([50, 10])
        for name, count in pools.most_common(25):
            _tbl_row(f"  {name[:48]:<48} {count:>10,d}")

    # ── Section 9: Virtual Threads ───────────────────────────────────────
    print_header("VIRTUAL THREADS (JDK 21+)")
    print_note("jdk.VirtualThreadPinned fires when a virtual thread blocks its carrier thread instead of yielding it (commonly a synchronized block, or native/JNI calls) — this is enabled by default with a 20ms threshold on JDK 21+. jdk.VirtualThreadStart/End are DISABLED by default, so a zero start/end count usually just means they weren't enabled, not that no virtual threads ran. Frequent or long pinning limits how many virtual threads your carrier pool can actually service concurrently.")
    print(f"\n  Pinning events: {analysis.vthread_pinned_count:,}   total pinned time: {analysis.vthread_pinned_total_ms:,.1f} ms")
    print(f"  VirtualThreadStart events: {analysis.vthread_start_count:,} (0 likely means not enabled, not 'no virtual threads')")
    top_pins = analysis.vthread_pinned_top(15)
    if top_pins:
        _tbl_title("Top Pinning Call Sites", 90)
        _tbl_hdr(f"  {'Call site (top 4 frames)':<60} {'Events':>8} {'Time (ms)':>13}")
        _tbl_sep([60, 8, 13])
        for sig, cnt, ms in top_pins:
            _tbl_row(f"  {sig[:58]:<58} {cnt:>8,d} {ms:>13,.1f}")

    # ── Section 10: Lock Contention ──────────────────────────────────────
    print_header("LOCK CONTENTION")
    print_note("Monitor enter = synchronized block/method waits (only recorded above a threshold, commonly 20ms by default); Thread park = java.util.concurrent lock waits. A park event is not inherently a problem — idle worker threads park constantly while waiting for work — judge by the stack trace and whether the thread was supposed to be busy.")
    print(f"\n  Monitor enter events: {len(analysis.monitor_enter_events):,}   "
          f"total wait: {analysis.monitor_contention_total_ms:,.1f} ms")
    top_mon = analysis.monitor_contention_top(20)
    if top_mon:
        _tbl_title("Top Contended Monitor Classes", 80)
        _tbl_hdr(f"  {'Class':<50} {'Wait (ms)':>13} {'Events':>10}")
        _tbl_sep([50, 13, 10])
        for cls, ms, cnt in top_mon:
            _tbl_row(f"  {cls[:48]:<48} {ms:>13,.1f} {cnt:>10,d}")

    print(f"\n  Thread park events: {len(analysis.thread_park_events):,}   "
          f"total park time: {analysis.thread_park_total_ms:,.1f} ms")
    top_park = analysis.thread_park_top(20)
    if top_park:
        _tbl_title("Top Parked Classes", 80)
        _tbl_hdr(f"  {'Class':<50} {'Park time (ms)':>16} {'Events':>10}")
        _tbl_sep([50, 16, 10])
        for cls, ms, cnt in top_park:
            _tbl_row(f"  {cls[:48]:<48} {ms:>16,.1f} {cnt:>10,d}")

    # ── Section 11: JIT Compilation ──────────────────────────────────────
    print_header("JIT COMPILATION")
    print_note("Compile time = CPU spent optimizing hot methods. High compile time during startup -> code churn as methods are compiled/recompiled. C1-only (TieredStopAtLevel=1) disables C2, trading peak throughput for faster startup & zero C2 compilation CPU. Level 0=interpreter, 1-3=C1 (increasing profiling), 4=C2 (most expensive, highest optimization).")
    print(f"\n  Compilations: {analysis.compilation_count:,}")
    print(f"  Total compile time: {analysis.compilation_total_ms:,.1f} ms")
    if analysis.recording_duration_s() > 0:
        pct_run = analysis.compilation_total_ms / 1000 / analysis.recording_duration_s() * 100
        print(f"  Compile time as % of recording: {pct_run:.2f}%")
    level_counts, level_times = analysis.compilation_by_level()
    if level_counts:
        _tbl_title("By Compile Level", 50)
        _tbl_hdr(f"  {'Level':>6} {'Count':>10} {'Time (ms)':>14}")
        _tbl_sep([6, 10, 14])
        for level in sorted(level_counts, key=lambda l: str(l)):
            _tbl_row(f"  {str(level):>6} {level_counts[level]:>10,d} {level_times[level]:>14,.1f}")
    top_compiled = analysis.compilation_top_methods(20)
    if top_compiled:
        _tbl_title("Top Compiled Methods by Time", 90)
        _tbl_hdr(f"  {'Method':<60} {'Level':>6} {'Time (ms)':>14}")
        _tbl_sep([60, 6, 14])
        for ms, method, level in top_compiled:
            _tbl_row(f"  {method[:58]:<58} {str(level):>6} {ms:>14,.2f}")

    # ── Section 12: I/O Activity ─────────────────────────────────────────
    print_header("SOCKET / FILE I/O ACTIVITY")
    print_note("I/O during startup delays readiness. Socket reads -> network calls (DB queries, HTTP clients). File reads -> classpath scanning, JAR access, config loading. Defer or cache network calls; use CDS to reduce file I/O from class loading.")
    sock = analysis.io_socket_summary()
    print(f"\n  Sockets — reads: {sock['read_count']:,} ({format_bytes(sock['read_bytes'])}, "
          f"{sock['read_ms']:,.1f} ms wait)")
    print(f"  Sockets — writes: {sock['write_count']:,} ({format_bytes(sock['write_bytes'])}, "
          f"{sock['write_ms']:,.1f} ms wait)")
    top_hosts = analysis.io_socket_top_hosts()
    if top_hosts:
        _tbl_title("Top Hosts by I/O Wait Time", 70)
        _tbl_hdr(f"  {'Host':<45} {'Wait (ms)':>15}")
        _tbl_sep([45, 15])
        for host, ms in top_hosts:
            _tbl_row(f"  {host[:43]:<43} {ms:>15,.1f}")

    fio = analysis.io_file_summary()
    print(f"\n  Files — reads: {fio['read_count']:,} ({format_bytes(fio['read_bytes'])}, "
          f"{fio['read_ms']:,.1f} ms wait)")
    print(f"  Files — writes: {fio['write_count']:,} ({format_bytes(fio['write_bytes'])}, "
          f"{fio['write_ms']:,.1f} ms wait)")
    top_paths = analysis.io_file_top_paths()
    if top_paths:
        _tbl_title("Top Paths by I/O Wait Time", 90)
        _tbl_hdr(f"  {'Path':<65} {'Wait (ms)':>15}")
        _tbl_sep([65, 15])
        for path, ms in top_paths:
            _tbl_row(f"  {path[:63]:<63} {ms:>15,.1f}")

    # ── Section 13: CPU Load Timeline ────────────────────────────────────
    print_header("CPU LOAD TIMELINE")
    print_note("JVM user% = app code CPU; system% = kernel time (I/O syscalls, some GC). Machine total near 100% -> CPU saturated. High system% relative to user% -> I/O or syscall bottleneck rather than pure computation. Correlate with I/O and GC sections.")
    avg_user, avg_sys, avg_machine = analysis.cpu_load_avg()
    print(f"\n  Avg JVM user: {avg_user:.1f}%   Avg JVM system: {avg_sys:.1f}%   Avg machine total: {avg_machine:.1f}%")
    cpu_series = analysis.cpu_load_series()
    if cpu_series:
        _tbl_hdr(f"\n  {'Timestamp':<22} {'JVM User':>9} {'JVM Sys':>9} {'Machine':>9}")
        _tbl_sep([22, 9, 9, 9])
        for ts, u, s, m in cpu_series[-20:]:
            _tbl_row(f"  {ts:<22} {u:>8.1f}% {s:>8.1f}% {m:>8.1f}%")

    # ── Section 14: Thread Idle Time ─────────────────────────────────────
    print_header("THREAD IDLE TIME (Thread.sleep + Object.wait)")
    print_note("Real JFR events jdk.ThreadSleep and jdk.JavaMonitorWait (java.util.concurrent parking is covered separately, in Lock Contention above). High idle on the main thread during startup -> blocked on an external resource or a latch. High idle on pool threads during a BUSY period -> the bottleneck is upstream of them, not in them.")
    idle_threads = analysis.idle_by_thread()
    total_idle = sum(idle_threads.values())
    print(f"\n  Total idle time across all threads: {total_idle/1000:.1f}s")
    print(f"  Sleep events: {len(analysis.sleep_events)}   Monitor-wait events: {len(analysis.wait_events)}")

    _tbl_title("By Thread", 70)
    _tbl_hdr(f"  {'Thread':<45} {'Time (ms)':>12} {'Pct':>7}")
    _tbl_sep([45, 12, 7])
    for t, d in idle_threads.most_common(20):
        pct = d / total_idle * 100 if total_idle else 0
        _tbl_row(f"  {t[:43]:<43} {d:>12,.0f} {pct:>6.1f}%")

    longest = analysis.idle_longest(15)
    if longest:
        _tbl_title("Longest Individual Idle Events", 80)
        _tbl_hdr(f"  {'Duration':>10} {'Kind':<6} {'Thread':<28} {'Top Frame':<40}")
        _tbl_sep([10, 6, 28, 40])
        for dur_ms, thread, top_frame, kind in longest:
            _tbl_row(f"  {dur_ms:>10,.0f} ms {kind:<6} {thread[:26]:<26} {top_frame[:38]:<38}")

    # ── Section 15: Exceptions ───────────────────────────────────────────
    print_header("EXCEPTIONS")
    print_note("Requires jdk.JavaExceptionThrow, which is NOT enabled under the default `profile` template on most JDK versions — an empty result below more often means 'not recorded' than 'no exceptions were thrown'. If you need this data, explicitly enable the event when starting the recording. Each throw costs real CPU for stack-trace capture, even when the exception is caught and handled — exception-driven control flow on a hot path is worth flagging.")
    print(f"\n  Exception throw events: {analysis.exception_count:,}")
    if analysis.exception_count == 0:
        print("  (Event not enabled for this recording, or genuinely zero exceptions.)")
    top_exc = analysis.exception_by_class(25)
    if top_exc:
        _tbl_title("Top Thrown Exception Classes", 70)
        _tbl_hdr(f"  {'Class':<50} {'Count':>10}")
        _tbl_sep([50, 10])
        for cls, cnt in top_exc:
            _tbl_row(f"  {cls[:48]:<48} {cnt:>10,d}")
    top_exc_stacks = analysis.exception_top_stacks(15)
    if top_exc_stacks:
        _tbl_title("Top Throw Sites (top 4 frames)", 90)
        for sig, cnt in top_exc_stacks:
            print(f"\n  [{cnt}x]")
            for line in sig.split(" -> "):
                print(f"    {line}")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                      BEFORE/AFTER COMPARISON                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


def report_comparison(before: JfrAnalysis, after: JfrAnalysis):
    """
    Print a side-by-side comparison of two JFR recordings.

    Compares all sections from report_single(), including the newer
    Allocation Rate, Safepoints, Metaspace, Virtual Threads, and
    Exceptions sections added alongside the correctness fixes.
    """
    print_header("BEFORE vs AFTER COMPARISON")
    print_note("Side-by-side delta view. ELIMINATED = was present in Before but absent in After. NEW = appeared only in After. Focus on large-magnitude deltas; small changes may be noise from slightly different workload timing or sampling variance. A valid comparison assumes the same workload, duration, JVM version, and GC algorithm in both recordings — a comparison across different collectors will show mostly noise in the GC section.")
    print(f"  Before: {before.name}  ({before.recording_duration_s():.3f}s, JVM {before.jvm_version()})")
    print(f"  After:  {after.name}  ({after.recording_duration_s():.3f}s, JVM {after.jvm_version()})")

    # ── Section 1: Allocation Comparison ─────────────────────────────────
    print_header("ALLOCATION COMPARISON (sampled)")
    print_note("Reduction in allocation -> less GC pressure, higher throughput. ELIMINATED (was >1MB, now 0) = clearest optimization wins. This is the sampled view; see Allocation Rate Comparison below for the TLAB-derived, near-total figure.")
    old_alloc = before.alloc_by_class()
    new_alloc = after.alloc_by_class()
    old_total = sum(old_alloc.values())
    new_total = sum(new_alloc.values())

    _tbl_hdr(f"\n  {'Metric':<48} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([48, 15, 15, 15])
    _tbl_row(f"  {'Total allocation (sampled)':<48} {format_bytes(old_total):>15} {format_bytes(new_total):>15} {format_bytes(new_total-old_total):>15}")
    _tbl_row(f"  {'Allocation samples':<48} {before.alloc_sample_count:>15,d} {after.alloc_sample_count:>15,d} {after.alloc_sample_count-before.alloc_sample_count:>+15,d}")

    _tbl_title("Top Allocation Types Comparison", 95)
    _tbl_hdr(f"  {'Type':<52} {'Before':>13} {'After':>13} {'Delta':>14}")
    _tbl_sep([52, 13, 13, 14])
    all_types = set(old_alloc) | set(new_alloc)
    for t in sorted(all_types, key=lambda t: old_alloc.get(t, 0), reverse=True)[:40]:
        o, n = old_alloc.get(t, 0), new_alloc.get(t, 0)
        delta = n - o
        if o == 0 and n == 0:
            continue
        marker = ""
        if o > 1_000_000 and n == 0:
            marker = " ◀◀ ELIMINATED"
        elif o == 0 and n > 1_000_000:
            marker = " ◀◀ NEW"
        _tbl_row(f"  {t[:50]:<50} {o:>13,d} {n:>13,d} {delta:>+14,d} ({pct_change(o, n)}){marker}")

    print_header("ALLOCATION RATE COMPARISON (TLAB-derived)")
    print_note("More reliable than the sampled comparison above for judging whether total allocation actually changed, since it's derived from near-exhaustive TLAB events rather than a statistical sample.")
    old_tlab, new_tlab = before.tlab_total_bytes, after.tlab_total_bytes
    old_rate, new_rate = before.allocation_rate_bytes_per_sec(), after.allocation_rate_bytes_per_sec()
    _tbl_hdr(f"\n  {'Metric':<40} {'Before':>18} {'After':>18} {'Change':>15}")
    _tbl_sep([40, 18, 18, 15])
    _tbl_row(f"  {'Total allocated (TLAB-derived)':<40} {format_bytes(old_tlab):>18} {format_bytes(new_tlab):>18} {pct_change(old_tlab, new_tlab):>15}")
    _tbl_row(f"  {'Allocation rate (bytes/sec)':<40} {format_bytes(old_rate)+'/s':>18} {format_bytes(new_rate)+'/s':>18} {pct_change(old_rate, new_rate):>15}")

    # ── Section 2: CPU Comparison ────────────────────────────────────────
    print_header("CPU EXECUTION SAMPLE COMPARISON")
    print_note("Fewer total samples for same duration -> less CPU time consumed. Method deltas show shifted hotspots. ◀◀ markers highlight methods significantly reduced or eliminated.")
    old_methods = before.cpu_method_counts()
    new_methods = after.cpu_method_counts()
    old_cpu_total = sum(old_methods.values())
    new_cpu_total = sum(new_methods.values())
    print(f"\n  Before: {int(old_cpu_total)} samples")
    print(f"  After:  {int(new_cpu_total)} samples")
    if old_cpu_total:
        print(f"  Delta:  {int(new_cpu_total - old_cpu_total):+d} ({pct_change(old_cpu_total, new_cpu_total)})")

    _tbl_title("Top Hot Methods Comparison", 90)
    _tbl_hdr(f"  {'Method':<65} {'Before':>8} {'After':>8} {'Delta':>8}")
    _tbl_sep([65, 8, 8, 8])
    all_methods = set(old_methods) | set(new_methods)
    for m in sorted(all_methods, key=lambda m: old_methods.get(m, 0), reverse=True)[:30]:
        o, n = old_methods.get(m, 0), new_methods.get(m, 0)
        delta = n - o
        marker = " ◀◀" if (o > 2 and n == 0) or (o >= 5 and delta <= -o * 0.5) else ""
        _tbl_row(f"  {m[:63]:<63} {o:>8} {n:>8} {delta:>+8}{marker}")

    _tbl_title("Thread Distribution Comparison", 90)
    _tbl_hdr(f"  {'Thread':<40} {'Before':>8} {'After':>8} {'Delta':>8}")
    _tbl_sep([40, 8, 8, 8])
    old_threads = before.cpu_thread_counts()
    new_threads = after.cpu_thread_counts()
    all_threads = set(old_threads) | set(new_threads)
    for t in sorted(all_threads, key=lambda t: old_threads.get(t, 0), reverse=True)[:15]:
        o, n = old_threads.get(t, 0), new_threads.get(t, 0)
        _tbl_row(f"  {t[:38]:<38} {o:>8} {n:>8} {n-o:>+8}")

    # ── Section 3: GC Heap Comparison ────────────────────────────────────
    print_header("GC / HEAP COMPARISON")
    print_note("Fewer GC events -> less allocation pressure. Lower peak heap -> reduced memory footprint. A tighter heap range means more stable memory usage.")
    old_heap = before.gc_heap_series()
    new_heap = after.gc_heap_series()
    if old_heap:
        print(f"\n  Before: {len(old_heap)} GC events, "
              f"heap {min(h[1] for h in old_heap):.1f} -> {max(h[1] for h in old_heap):.1f} MB")
    else:
        print("\n  Before: no GC data")
    if new_heap:
        print(f"  After:  {len(new_heap)} GC events, "
              f"heap {min(h[1] for h in new_heap):.1f} -> {max(h[1] for h in new_heap):.1f} MB")
    else:
        print("  After:  no GC data")
    if old_heap and new_heap:
        print(f"  GC event count change: {len(new_heap) - len(old_heap):+d} ({pct_change(len(old_heap), len(new_heap))})")

    # ── Section 4: GC Pause Time Comparison ──────────────────────────────
    print_header("GC PAUSE TIME COMPARISON")
    print_note("Reduced pause count/time -> better responsiveness. Compare by-phase to see which GC phase improved. The young/old split is a naming heuristic — treat as directional, not exact, especially if comparing different collectors.")
    ob = before.gc_pause_stats()
    oa = after.gc_pause_stats()
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([30, 15, 15, 15])
    _tbl_row(f"  {'Pause count':<30} {ob['count']:>15,d} {oa['count']:>15,d} {oa['count']-ob['count']:>+15,d}")
    _tbl_row(f"  {'Total pause (ms)':<30} {ob['total_ms']:>15,.1f} {oa['total_ms']:>15,.1f} {oa['total_ms']-ob['total_ms']:>+15,.1f}")
    _tbl_row(f"  {'Avg pause (ms)':<30} {ob['avg_ms']:>15,.2f} {oa['avg_ms']:>15,.2f} {oa['avg_ms']-ob['avg_ms']:>+15,.2f}")
    _tbl_row(f"  {'Max pause (ms)':<30} {ob['max_ms']:>15,.2f} {oa['max_ms']:>15,.2f} {oa['max_ms']-ob['max_ms']:>+15,.2f}")

    old_young, old_old, old_other = before.gc_pause_generation_split()
    new_young, new_old, new_other = after.gc_pause_generation_split()
    _tbl_row(f"  {'Young-gen pause (ms, heuristic)':<30} {old_young:>15,.1f} {new_young:>15,.1f} {new_young-old_young:>+15,.1f}")
    _tbl_row(f"  {'Old/full pause (ms, heuristic)':<30} {old_old:>15,.1f} {new_old:>15,.1f} {new_old-old_old:>+15,.1f}")

    old_phase = before.gc_pause_by_phase()
    new_phase = after.gc_pause_by_phase()
    all_phases = set(old_phase) | set(new_phase)
    if all_phases:
        _tbl_title("By Phase (ms)", 70)
        _tbl_hdr(f"  {'Phase':<35} {'Before':>12} {'After':>12} {'Delta':>12}")
        _tbl_sep([35, 12, 12, 12])
        for phase in sorted(all_phases, key=lambda p: old_phase.get(p, 0), reverse=True):
            o, n = old_phase.get(phase, 0), new_phase.get(phase, 0)
            _tbl_row(f"  {phase[:33]:<33} {o:>12,.1f} {n:>12,.1f} {n-o:>+12,.1f}")

    # ── Section 5: Safepoint Comparison ──────────────────────────────────
    print_header("SAFEPOINT COMPARISON")
    print_note("Overlaps with GC pause time above — a matching delta in both usually just means GC drove the change; a safepoint delta with little/no matching GC delta points at non-GC safepoint causes.")
    sp_o, sp_n = before.safepoint_total_ms, after.safepoint_total_ms
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([30, 15, 15, 15])
    _tbl_row(f"  {'Total safepoint time (ms)':<30} {sp_o:>15,.1f} {sp_n:>15,.1f} {sp_n-sp_o:>+15,.1f}")

    # ── Section 6: Class Loading + Metaspace Comparison ──────────────────
    print_header("CLASS LOADING & METASPACE COMPARISON")
    print_note("Fewer classes loaded -> faster startup & less metadata memory. Large reductions suggest dependency trimming or build-time/AOT processing is working.")
    ol, ou = before.class_loading_final()
    nl, nu = after.class_loading_final()
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([30, 15, 15, 15])
    _tbl_row(f"  {'Classes loaded':<30} {ol:>15,d} {nl:>15,d} {nl-ol:>+15,d} ({pct_change(ol, nl)})")
    _tbl_row(f"  {'Classes unloaded':<30} {ou:>15,d} {nu:>15,d} {nu-ou:>+15,d} ({pct_change(ou, nu)})")
    op_used, op_committed = before.metaspace_peak()
    np_used, np_committed = after.metaspace_peak()
    if op_committed or np_committed:
        _tbl_row(f"  {'Metaspace peak used':<30} {format_bytes(op_used):>15} {format_bytes(np_used):>15} {pct_change(op_used, np_used):>15}")
        _tbl_row(f"  {'Metaspace peak committed':<30} {format_bytes(op_committed):>15} {format_bytes(np_committed):>15} {pct_change(op_committed, np_committed):>15}")

    # ── Section 7: Thread Creation Comparison ────────────────────────────
    print_header("THREAD CREATION COMPARISON")
    print_note("Fewer threads started -> less overhead from stack allocation & context switching. Pool breakdown changes show which subsystems now have different activity levels.")
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([30, 15, 15, 15])
    _tbl_row(f"  {'Threads started':<30} {before.thread_start_count:>15,d} {after.thread_start_count:>15,d} "
             f"{after.thread_start_count-before.thread_start_count:>+15,d} ({pct_change(before.thread_start_count, after.thread_start_count)})")
    _tbl_row(f"  {'Threads ended':<30} {before.thread_end_count:>15,d} {after.thread_end_count:>15,d} "
             f"{after.thread_end_count-before.thread_end_count:>+15,d}")

    old_pools = before.thread_pool_breakdown()
    new_pools = after.thread_pool_breakdown()
    all_pools = set(old_pools) | set(new_pools)
    if all_pools:
        _tbl_title("By Pool / Name Prefix", 70)
        _tbl_hdr(f"  {'Pool / prefix':<40} {'Before':>10} {'After':>10} {'Delta':>10}")
        _tbl_sep([40, 10, 10, 10])
        for p in sorted(all_pools, key=lambda p: old_pools.get(p, 0), reverse=True)[:25]:
            o, n = old_pools.get(p, 0), new_pools.get(p, 0)
            _tbl_row(f"  {p[:38]:<38} {o:>10,d} {n:>10,d} {n-o:>+10,d}")

    # ── Section 8: Virtual Thread Comparison ─────────────────────────────
    print_header("VIRTUAL THREAD COMPARISON")
    print_note("A reduction in pinning events/time after a change (e.g., replacing a synchronized block with ReentrantLock, or upgrading past JEP 491) is a genuine win for carrier-thread scalability.")
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([30, 15, 15, 15])
    _tbl_row(f"  {'Pinning events':<30} {before.vthread_pinned_count:>15,d} {after.vthread_pinned_count:>15,d} "
             f"{after.vthread_pinned_count-before.vthread_pinned_count:>+15,d}")
    _tbl_row(f"  {'Pinned time (ms)':<30} {before.vthread_pinned_total_ms:>15,.1f} {after.vthread_pinned_total_ms:>15,.1f} "
             f"{after.vthread_pinned_total_ms-before.vthread_pinned_total_ms:>+15,.1f}")

    # ── Section 9: Lock Contention Comparison ────────────────────────────
    print_header("LOCK CONTENTION COMPARISON")
    print_note("Reduced wait time -> less thread blocking. ELIMINATED classes are the biggest wins — contention fully removed.")
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([30, 15, 15, 15])
    _tbl_row(f"  {'Monitor enter events':<30} {len(before.monitor_enter_events):>15,d} {len(after.monitor_enter_events):>15,d} "
             f"{len(after.monitor_enter_events)-len(before.monitor_enter_events):>+15,d}")
    _tbl_row(f"  {'Monitor wait time (ms)':<30} {before.monitor_contention_total_ms:>15,.1f} {after.monitor_contention_total_ms:>15,.1f} "
             f"{after.monitor_contention_total_ms-before.monitor_contention_total_ms:>+15,.1f}")
    _tbl_row(f"  {'Thread park events':<30} {len(before.thread_park_events):>15,d} {len(after.thread_park_events):>15,d} "
             f"{len(after.thread_park_events)-len(before.thread_park_events):>+15,d}")
    _tbl_row(f"  {'Park time (ms)':<30} {before.thread_park_total_ms:>15,.1f} {after.thread_park_total_ms:>15,.1f} "
             f"{after.thread_park_total_ms-before.thread_park_total_ms:>+15,.1f}")

    old_mon = dict((c, ms) for c, ms, _ in before.monitor_contention_top(100))
    new_mon = dict((c, ms) for c, ms, _ in after.monitor_contention_top(100))
    all_mon = set(old_mon) | set(new_mon)
    if all_mon:
        _tbl_title("Top Contended Monitor Classes (ms)", 80)
        _tbl_hdr(f"  {'Class':<45} {'Before':>13} {'After':>13} {'Delta':>13}")
        _tbl_sep([45, 13, 13, 13])
        for cls in sorted(all_mon, key=lambda c: old_mon.get(c, 0), reverse=True)[:20]:
            o, n = old_mon.get(cls, 0), new_mon.get(cls, 0)
            marker = " ◀◀ ELIMINATED" if o > 0 and n == 0 else ""
            _tbl_row(f"  {cls[:43]:<43} {o:>13,.1f} {n:>13,.1f} {n-o:>+13,.1f}{marker}")

    # ── Section 10: JIT Compilation Comparison ───────────────────────────
    print_header("JIT COMPILATION COMPARISON")
    print_note("Fewer compilations / less compile time -> less CPU spent on JIT. With TieredStopAtLevel=1, C2 (level 4) compilations disappear entirely.")
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([30, 15, 15, 15])
    _tbl_row(f"  {'Compilations':<30} {before.compilation_count:>15,d} {after.compilation_count:>15,d} "
             f"{after.compilation_count-before.compilation_count:>+15,d} ({pct_change(before.compilation_count, after.compilation_count)})")
    _tbl_row(f"  {'Total compile time (ms)':<30} {before.compilation_total_ms:>15,.1f} {after.compilation_total_ms:>15,.1f} "
             f"{after.compilation_total_ms-before.compilation_total_ms:>+15,.1f} ({pct_change(before.compilation_total_ms, after.compilation_total_ms)})")

    old_lvl_counts, old_lvl_times = before.compilation_by_level()
    new_lvl_counts, new_lvl_times = after.compilation_by_level()
    all_levels = set(old_lvl_counts) | set(new_lvl_counts)
    if all_levels:
        _tbl_title("By Compile Level", 60)
        _tbl_hdr(f"  {'Level':>6} {'Before ct':>10} {'After ct':>10} {'Before ms':>11} {'After ms':>11}")
        _tbl_sep([6, 10, 10, 11, 11])
        for level in sorted(all_levels, key=lambda l: str(l)):
            _tbl_row(f"  {str(level):>6} {old_lvl_counts.get(level,0):>10,d} {new_lvl_counts.get(level,0):>10,d} "
                     f"{old_lvl_times.get(level,0):>11,.1f} {new_lvl_times.get(level,0):>11,.1f}")

    # ── Section 11: I/O Comparison ───────────────────────────────────────
    print_header("SOCKET / FILE I/O COMPARISON")
    print_note("Reduced I/O -> faster readiness & less waiting. Socket changes may reflect different workload; file I/O changes reflect classpath/config scanning activity.")
    os_ = before.io_socket_summary()
    ns_ = after.io_socket_summary()
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>18} {'After':>18} {'Change':>15}")
    _tbl_sep([30, 18, 18, 15])
    _tbl_row(f"  {'Socket reads':<30} {os_['read_count']:>18,d} {ns_['read_count']:>18,d} {ns_['read_count']-os_['read_count']:>+15,d}")
    _tbl_row(f"  {'Socket bytes read':<30} {format_bytes(os_['read_bytes']):>18} {format_bytes(ns_['read_bytes']):>18} {format_bytes(ns_['read_bytes']-os_['read_bytes']):>15}")
    _tbl_row(f"  {'Socket writes':<30} {os_['write_count']:>18,d} {ns_['write_count']:>18,d} {ns_['write_count']-os_['write_count']:>+15,d}")
    _tbl_row(f"  {'Socket bytes written':<30} {format_bytes(os_['write_bytes']):>18} {format_bytes(ns_['write_bytes']):>18} {format_bytes(ns_['write_bytes']-os_['write_bytes']):>15}")

    of_ = before.io_file_summary()
    nf_ = after.io_file_summary()
    _tbl_row(f"\n  {'File reads':<30} {of_['read_count']:>18,d} {nf_['read_count']:>18,d} {nf_['read_count']-of_['read_count']:>+15,d}")
    _tbl_row(f"  {'File bytes read':<30} {format_bytes(of_['read_bytes']):>18} {format_bytes(nf_['read_bytes']):>18} {format_bytes(nf_['read_bytes']-of_['read_bytes']):>15}")
    _tbl_row(f"  {'File writes':<30} {of_['write_count']:>18,d} {nf_['write_count']:>18,d} {nf_['write_count']-of_['write_count']:>+15,d}")
    _tbl_row(f"  {'File bytes written':<30} {format_bytes(of_['write_bytes']):>18} {format_bytes(nf_['write_bytes']):>18} {format_bytes(nf_['write_bytes']-of_['write_bytes']):>15}")

    # ── Section 12: CPU Load Comparison ──────────────────────────────────
    print_header("CPU LOAD COMPARISON")
    print_note("Lower JVM user% -> less CPU time for same work. Lower system% -> fewer I/O syscalls. A shift from user->system may indicate I/O is now the bottleneck rather than computation.")
    ou_, os2, om = before.cpu_load_avg()
    nu_, ns2, nm = after.cpu_load_avg()
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>12} {'After':>12} {'Change':>12}")
    _tbl_sep([30, 12, 12, 12])
    _tbl_row(f"  {'Avg JVM user %':<30} {ou_:>11.1f}% {nu_:>11.1f}% {nu_-ou_:>+11.1f}%")
    _tbl_row(f"  {'Avg JVM system %':<30} {os2:>11.1f}% {ns2:>11.1f}% {ns2-os2:>+11.1f}%")
    _tbl_row(f"  {'Avg machine total %':<30} {om:>11.1f}% {nm:>11.1f}% {nm-om:>+11.1f}%")

    # ── Section 13: Idle Time Comparison ─────────────────────────────────
    print_header("THREAD IDLE TIME COMPARISON")
    print_note("Less idle time -> threads spending less time waiting (sleep/monitor-wait; java.util.concurrent parking is compared separately above). Sleep/wait on the main thread specifically -> startup blocked on an external resource.")
    old_idle = before.idle_by_thread()
    new_idle = after.idle_by_thread()
    old_idle_total = sum(old_idle.values())
    new_idle_total = sum(new_idle.values())
    print(f"\n  Before: {len(before.sleep_events) + len(before.wait_events)} events, {old_idle_total/1000:.1f}s total")
    print(f"  After:  {len(after.sleep_events) + len(after.wait_events)} events, {new_idle_total/1000:.1f}s total")

    _tbl_hdr(f"\n  {'Thread':<40} {'Before (ms)':>12} {'After (ms)':>12} {'Delta':>12}")
    _tbl_sep([40, 12, 12, 12])
    all_idle_threads = set(old_idle) | set(new_idle)
    for t in sorted(all_idle_threads, key=lambda t: old_idle.get(t, 0), reverse=True)[:15]:
        o, n = old_idle.get(t, 0), new_idle.get(t, 0)
        _tbl_row(f"  {t[:38]:<38} {o:>12,.0f} {n:>12,.0f} {n-o:>+12,.0f}")

    # ── Section 14: Exception Comparison ─────────────────────────────────
    print_header("EXCEPTION COMPARISON")
    print_note("Only meaningful if jdk.JavaExceptionThrow was enabled in BOTH recordings — otherwise a delta here just reflects a settings difference, not a behavior change.")
    _tbl_hdr(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    _tbl_sep([30, 15, 15, 15])
    _tbl_row(f"  {'Exceptions thrown':<30} {before.exception_count:>15,d} {after.exception_count:>15,d} "
             f"{after.exception_count-before.exception_count:>+15,d} ({pct_change(before.exception_count, after.exception_count)})")

    # ── Section 15: Overall Summary ──────────────────────────────────────
    print_header("SUMMARY")
    print_note("Key metrics at a glance. Green flags: reduced allocation, lower GC pause, fewer classes loaded, less lock contention, shorter duration. Red flags: increases in any of these may indicate regression or a different workload — always sanity-check against Recording Metadata for both files before trusting a delta.")
    dur_delta = after.recording_duration_s() - before.recording_duration_s()
    print(f"\n  Recording duration: {before.recording_duration_s():.3f}s -> {after.recording_duration_s():.3f}s "
          f"({dur_delta:+.3f}s, {pct_change(before.recording_duration_s(), after.recording_duration_s())})")
    print(f"  Allocation (sampled): {format_bytes(old_total)} -> {format_bytes(new_total)} ({pct_change(old_total, new_total)})")
    print(f"  Allocation rate (TLAB-derived): {format_bytes(old_rate)}/s -> {format_bytes(new_rate)}/s ({pct_change(old_rate, new_rate)})")
    print(f"  GC pause time: {ob['total_ms']:,.1f} ms -> {oa['total_ms']:,.1f} ms ({pct_change(ob['total_ms'], oa['total_ms'])})")
    print(f"  Safepoint time: {sp_o:,.1f} ms -> {sp_n:,.1f} ms ({pct_change(sp_o, sp_n)})")
    print(f"  JIT compile time: {before.compilation_total_ms:,.1f} ms -> {after.compilation_total_ms:,.1f} ms "
          f"({pct_change(before.compilation_total_ms, after.compilation_total_ms)})")
    print(f"  Classes loaded: {ol:,} -> {nl:,} ({pct_change(ol, nl)})")
    print(f"  Threads started: {before.thread_start_count:,} -> {after.thread_start_count:,} "
          f"({pct_change(before.thread_start_count, after.thread_start_count)})")
    print(f"  Virtual thread pinning events: {before.vthread_pinned_count:,} -> {after.vthread_pinned_count:,} "
          f"({pct_change(before.vthread_pinned_count, after.vthread_pinned_count)})")
    print(f"  Lock wait time: {before.monitor_contention_total_ms:,.1f} ms -> {after.monitor_contention_total_ms:,.1f} ms "
          f"({pct_change(before.monitor_contention_total_ms, after.monitor_contention_total_ms)})")
    print(f"  Thread idle time: {old_idle_total/1000:.1f}s -> {new_idle_total/1000:.1f}s "
          f"({pct_change(old_idle_total, new_idle_total)})")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                            ENTRY POINT                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


def main():
    """
    Parse command-line arguments and dispatch to the appropriate report.

    Modes:
      - 1 argument:  Single-file analysis (full report with all sections).
      - 2 arguments: Before/after comparison (single reports + diff report).
      - 0 or >2:     Print usage and exit.
    """
    global MARKDOWN

    # Parse --markdown / -m flag from any position in args
    args = [a for a in sys.argv[1:] if a not in ("--markdown", "-m")]
    if len(args) < len(sys.argv) - 1:
        MARKDOWN = True

    if len(args) < 1:
        print(__doc__)
        sys.exit(1)

    files = args

    if len(files) == 1:
        analysis = JfrAnalysis(files[0])
        report_single(analysis)

    elif len(files) == 2:
        before = JfrAnalysis(files[0])
        after = JfrAnalysis(files[1])
        report_single(before)
        report_single(after)
        report_comparison(before, after)

    else:
        print("ERROR: Provide 1 JFR file (single analysis) or 2 JFR files (comparison).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
