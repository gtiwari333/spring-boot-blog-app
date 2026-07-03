#!/usr/bin/env python3
"""
JFR (Java Flight Recorder) Startup Analyzer
============================================
Analyzes one or two JFR recordings to identify startup bottlenecks and
compare before/after optimizations.

Take JFR from running JVM app
- Use JMC 'sdk install jmc'
- use intellij 
- or use jcmd command as  `$ jcmd <PID> JFR.start settings=profile name=<NAME>``


Usage:
  python3 jfr-analyzer.py <file.jfr>                 # Single file analysis
  python3 jfr-analyzer.py <before.jfr> <after.jfr>   # Before/after comparison

Requirements:
  - Java 21+ with `jfr` CLI tool on PATH
  - Python 3.10+

Output:
  - Recording metadata (JVM version/args, PID, duration, chunks)
  - CPU execution hot spots (method-level and full stack traces)
  - Memory allocation hotspots by type and allocation site
  - GC / heap behavior timeline + GC pause-time breakdown by phase
  - Class loading (loaded/unloaded counts)
  - Thread creation (counts, pool grouping)
  - Lock contention (monitor enter waits, thread park waits)
  - JIT compilation time (total + top compiled methods)
  - Socket / file I/O activity (bytes + wait time)
  - CPU load timeline (JVM vs machine)
  - Wall clock sleeping / thread idle analysis
  - Side-by-side comparison (when two files are provided) for every section
    above, with deltas and ELIMINATED / NEW markers.


What It Analyzes

    ┌───────────────────────┬────────────────────────────────┬──────────────────────────────────────────────────────────┐
    │ Section               │ Data Source                    │ What It Shows                                            │
    ├───────────────────────┼────────────────────────────────┼──────────────────────────────────────────────────────────┤
    │ Recording Metadata    │ `jfr summary` + JVMInfo        │ JVM version, PID, duration, chunks                      │
    │ CPU Hotspots          │ jdk.ExecutionSample            │ Top 30 hot leaf methods, thread distribution, top stacks│
    │ Allocation Hotspots   │ jdk.ObjectAllocationSample     │ Top 40 allocation types, top byte[] allocation sites    │
    │ GC/Heap Timeline      │ jdk.GCHeapSummary              │ Heap growth over time, peak usage                       │
    │ GC Pause Times        │ jdk.GCPhasePause               │ Pause count/total/avg/max, breakdown by phase name      │
    │ Class Loading         │ jdk.ClassLoadingStatistics     │ Loaded/unloaded class counts over time, final totals    │
    │ Thread Creation       │ jdk.ThreadStart / ThreadEnd    │ Threads started, grouped by pool/name prefix            │
    │ Lock Contention       │ jdk.JavaMonitorEnter/ThreadPark│ Top contended monitor classes, top parked classes       │
    │ JIT Compilation       │ jdk.Compilation                │ Total compile time, top compiled methods by time        │
    │ Socket / File I/O     │ jdk.SocketRead/Write, File*    │ Bytes transferred + wait time, top hosts/paths          │
    │ CPU Load Timeline     │ jdk.CPULoad                    │ JVM user/system vs whole-machine CPU over time          │
    │ Wall Clock Sleeping   │ profiler.WallClockSleeping     │ Idle/wait time by thread, longest individual sleep      │
    │ Comparison Mode       │ Both files                     │ Delta tables for every section (ELIMINATED/NEW markers) │
    └───────────────────────┴────────────────────────────────┴──────────────────────────────────────────────────────────┘


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

  Other Sections:
    - High GC pause time          →  Too many allocations; check allocation hotspots first
    - High class loading count    →  Too many dependencies; trim classpath or use CDS
    - Lock contention on main     →  Bottleneck in synchronized code; consider lock-free structures
    - High JIT compile time       →  Code churn during startup; C1-only tiered compilation helps
    - High socket I/O             →  Network calls during startup; defer or cache
    - High file I/O               →  File scanning (JARs, classpath); use CDS or indexer

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

    Handles ISO 8601 strings ("PT0.328702567S") and raw nanosecond integers.
    """
    if dur is None or dur == 0:
        return 0.0
    if isinstance(dur, (int, float)):
        return float(dur) / 1_000_000  # nanos → ms
    if isinstance(dur, str):
        m = re.match(r"PT([\d.]+)S", dur)
        if m:
            return float(m.group(1)) * 1000  # seconds → ms
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


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                     JFR DATA MODEL (JfrAnalysis)                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


class JfrAnalysis:
    """
    Parsed and queryable data from a single JFR recording.

    Extracts these JFR event types from the binary .jfr file:

    ┌────────────────────────────────┬─────────────────────────────────────────────┐
    │ Event Type                     │ What It Captures                            │
    ├────────────────────────────────┼─────────────────────────────────────────────┤
    │ jdk.ExecutionSample (text)     │ Periodic thread dumps → CPU hotspots        │
    │ jdk.ObjectAllocationSample     │ Sampled allocations → memory churn          │
    │ jdk.ObjectAllocationInNewTLAB  │ TLAB creation events → allocation pressure  │
    │ profiler.WallClockSleeping     │ Thread idle/wait periods → I/O bottlenecks  │
    │ jdk.GCHeapSummary              │ Heap usage snapshots → growth curve         │
    │ jdk.GCPhasePause               │ Stop-the-world pause durations → GC impact  │
    │ jdk.ClassLoadingStatistics     │ Cumulative class load/unload counts         │
    │ jdk.ThreadStart / ThreadEnd    │ Thread lifecycle → threading overhead        │
    │ jdk.JavaMonitorEnter           │ Synchronized block waits → lock contention  │
    │ jdk.ThreadPark                 │ Parked threads → java.util.concurrent waits │
    │ jdk.Compilation                │ JIT compiler activity → compile-time cost   │
    │ jdk.SocketRead / SocketWrite   │ Network I/O volume + wait time              │
    │ jdk.FileRead / FileWrite       │ File I/O volume + wait time                 │
    │ jdk.CPULoad                    │ JVM/machine CPU utilization over time       │
    │ jdk.JVMInformation             │ JVM version, flags, PID                     │
    └────────────────────────────────┴─────────────────────────────────────────────┘
    """

    def __init__(self, jfr_file: str):
        self.file = jfr_file
        self.name = Path(jfr_file).stem

        # ── Core event collections ───────────────────────────────────────
        self.cpu_samples: list[dict] = []
        self.alloc_samples: list[dict] = []
        self.tlab_samples: list[dict] = []
        self.sleep_events: list[dict] = []
        self.gc_events: list[dict] = []

        # ── Extended event collections (v2) ───────────────────────────────
        self.gc_pause_events: list[dict] = []
        self.class_loading_events: list[dict] = []
        self.thread_start_events: list[dict] = []
        self.thread_end_events: list[dict] = []
        self.monitor_enter_events: list[dict] = []
        self.thread_park_events: list[dict] = []
        self.compilation_events: list[dict] = []
        self.socket_read_events: list[dict] = []
        self.socket_write_events: list[dict] = []
        self.file_read_events: list[dict] = []
        self.file_write_events: list[dict] = []
        self.cpu_load_events: list[dict] = []

        # ── Metadata ─────────────────────────────────────────────────────
        self.jvm_info: dict = {}
        self.summary_text: str = ""

        self._load()

    # ── Data Loading Helpers ──────────────────────────────────────────────

    def _try_json(self, event_type: str) -> list:
        """
        Safely load a JSON event type, returning [] on any error.

        Many JFR event types are conditionally enabled based on recording
        settings. This helper prevents one missing event type from blocking
        the entire analysis.
        """
        try:
            data = jfr_print_json(self.file, event_type)
            return data.get("recording", {}).get("events", [])
        except Exception as e:
            print(f"  [WARN] {event_type}: {e}", file=sys.stderr)
            return []

    def _load(self):
        """
        Extract all 15+ event types from the JFR file.

        Each extraction is independent — failure in one does not block others.
        CPU samples use text mode for richer, faster-to-parse stack traces.
        All other events use JSON mode for numeric precision.
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

        # ── Core event types (JSON) ──────────────────────────────────────
        self.alloc_samples = self._try_json("jdk.ObjectAllocationSample")

        try:
            data = jfr_print_json(self.file, "jdk.ObjectAllocationInNewTLAB")
            self.tlab_samples = data.get("recording", {}).get("events", [])
        except Exception:
            pass  # TLAB data is supplementary, silent skip

        self.sleep_events = self._try_json("profiler.WallClockSleeping")

        try:
            data = jfr_print_json(self.file, "jdk.GCHeapSummary")
            self.gc_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass  # Optional

        # ── Extended event types (v2) ────────────────────────────────────
        # GC pause phases — actual stop-the-world pause durations by phase
        try:
            data = jfr_print_json(self.file, "jdk.GCPhasePause")
            self.gc_pause_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass

        # Class loading statistics — cumulative loaded/unloaded counters
        try:
            data = jfr_print_json(self.file, "jdk.ClassLoadingStatistics")
            self.class_loading_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass

        # Thread lifecycle — start and end events
        try:
            data = jfr_print_json(self.file, "jdk.ThreadStart")
            self.thread_start_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass
        try:
            data = jfr_print_json(self.file, "jdk.ThreadEnd")
            self.thread_end_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass

        # Lock contention — synchronized block waits + park events
        try:
            data = jfr_print_json(self.file, "jdk.JavaMonitorEnter")
            self.monitor_enter_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass
        try:
            data = jfr_print_json(self.file, "jdk.ThreadPark")
            self.thread_park_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass

        # JIT compilation — which methods are being compiled and how long
        try:
            data = jfr_print_json(self.file, "jdk.Compilation")
            self.compilation_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass

        # Socket I/O — network reads and writes
        try:
            data = jfr_print_json(self.file, "jdk.SocketRead")
            self.socket_read_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass
        try:
            data = jfr_print_json(self.file, "jdk.SocketWrite")
            self.socket_write_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass

        # File I/O — disk reads and writes
        try:
            data = jfr_print_json(self.file, "jdk.FileRead")
            self.file_read_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass
        try:
            data = jfr_print_json(self.file, "jdk.FileWrite")
            self.file_write_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass

        # CPU load timeline — JVM vs machine load over time
        try:
            data = jfr_print_json(self.file, "jdk.CPULoad")
            self.cpu_load_events = data.get("recording", {}).get("events", [])
        except Exception:
            pass

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

    # ── Allocation Accessors ─────────────────────────────────────────────

    def alloc_by_class(self) -> Counter:
        """
        Sum allocation weight (bytes) by object class name.

        Uses dig() for safe nested access since the objectClass structure
        varies between JDK versions.
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
                sig = " -> ".join(
                    f"{dig(f, 'method', 'type', 'name', default='?')}.{dig(f, 'method', 'name', default='?')}"[:80]
                    for f in frames[:depth]
                )
                c[sig] += weight
        return c

    @property
    def total_alloc_bytes(self) -> int:
        return sum(self.alloc_by_class().values())

    @property
    def cpu_sample_count(self) -> int:
        return len(self.cpu_samples)

    @property
    def alloc_sample_count(self) -> int:
        return len(self.alloc_samples)

    # ── Sleep Accessors ──────────────────────────────────────────────────

    def sleep_by_thread(self) -> Counter:
        """Total sleep duration (ms) by thread name."""
        c: Counter[str] = Counter()
        for e in self.sleep_events:
            v = e["values"]
            t = dig(v, "eventThread", "javaName", default="?")
            c[t] += parse_duration_iso(v.get("duration", 0))
        return c

    def sleep_longest(self, n: int = 15) -> list[tuple[float, str, str, int]]:
        """Top N longest individual sleep events with thread and top frame."""
        sorted_events = sorted(
            self.sleep_events,
            key=lambda e: parse_duration_iso(e["values"].get("duration", 0)),
            reverse=True,
        )
        result: list[tuple[float, str, str, int]] = []
        for e in sorted_events[:n]:
            v = e["values"]
            dur_ms = parse_duration_iso(v.get("duration", 0))
            frames = dig(v, "stackTrace", "frames", default=[])
            top_frame = (
                f"{dig(frames[0], 'method', 'type', 'name', default='?')}.{dig(frames[0], 'method', 'name', default='?')}"
                if frames else "unknown"
            )
            thread = dig(v, "eventThread", "javaName", default="?")
            samples = v.get("samplesCount", "?")
            result.append((dur_ms, thread, top_frame, samples))
        return result

    @property
    def total_sleep_ms(self) -> float:
        return sum(self.sleep_by_thread().values())

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
        indicate which type of collection is consuming time.  Many young
        pauses = heavy short-lived allocation churn.  Any full pause =
        potentially problematic old-gen pressure.
        """
        c: Counter[str] = Counter()
        for e in self.gc_pause_events:
            v = e["values"]
            name = v.get("name", "unknown")
            c[name] += parse_duration_iso(v.get("duration", 0))
        return c

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
        together under "http-nio-8080-exec".
        """
        c: Counter[str] = Counter()
        for e in self.thread_start_events:
            v = e["values"]
            name = dig(v, "thread", "javaName", default="unknown")
            norm = re.sub(r"[-#]?\d+$", "", name).strip() or name
            c[norm] += 1
        return c

    # ── Lock Contention Accessors ────────────────────────────────────────

    def monitor_contention_top(self, n: int = 20) -> list[tuple[str, float, int]]:
        """
        Top N contended monitor (synchronized) classes by total wait time.

        Returns list of (class_name, total_wait_ms, event_count).
        High wait time on a class means multiple threads are contending
        for a synchronized block/method on that class.
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
        ReentrantLock, CountDownLatch, park/unpark).  High park time
        indicates threads waiting on concurrent primitives.
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
        """Total time spent in JIT compilation.  High values during startup
        indicate the JIT is working hard to compile hot methods."""
        return sum(parse_duration_iso(e["values"].get("duration", 0)) for e in self.compilation_events)

    @property
    def compilation_count(self) -> int:
        return len(self.compilation_events)

    def compilation_top_methods(self, n: int = 20) -> list[tuple[float, str, str]]:
        """
        Top N methods by compilation time.

        Returns list of (time_ms, method_signature, compile_level).
        Compile level indicates optimization tier (e.g., 3=C1, 4=C2).
        """
        rows = []
        for e in self.compilation_events:
            v = e["values"]
            dur = parse_duration_iso(v.get("duration", 0))
            method = f"{dig(v, 'method', 'type', 'name', default='?')}.{dig(v, 'method', 'name', default='?')}"
            level = v.get("compileLevel", "?")
            rows.append((dur, method, level))
        rows.sort(key=lambda r: r[0], reverse=True)
        return rows[:n]

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


def print_header(title: str):
    """Print a centered, double-lined section header."""
    print()
    print("=" * SECTION_WIDTH)
    print(f"{title:^{SECTION_WIDTH}}")
    print("=" * SECTION_WIDTH)


def print_subheader(title: str):
    """Print a subsection header with underline."""
    print(f"\n{title}")
    print("-" * min(SECTION_WIDTH, len(title)))


def report_single(analysis: JfrAnalysis):
    """
    Print a complete analysis report for a single JFR file.

    Report sections (in order):
    1.  Recording Metadata — JVM version, args, PID, duration
    2.  CPU Execution Hotspots — leaf methods, threads, stack signatures
    3.  Memory Allocation Hotspots — by type, byte[] allocation sites
    4.  GC / Heap Timeline — heap growth curve
    5.  GC Pause Times — pause statistics by phase
    6.  Class Loading — loaded/unloaded counts
    7.  Thread Creation — start/end counts, pool breakdown
    8.  Lock Contention — monitor enter + thread park top classes
    9.  JIT Compilation — total time + top compiled methods
    10. Socket / File I/O — bytes transferred, wait times, top hosts/paths
    11. CPU Load Timeline — JVM vs machine CPU over time
    12. Wall Clock Sleeping — idle/wait by thread, longest individual events
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
    methods = analysis.cpu_method_counts()
    total = sum(methods.values()) or 1
    print(f"\n  Total samples: {int(total)}")
    print(f"\n  {'Top 30 Hot Leaf Methods':^80}")
    print(f"  {'Method':<70} {'Count':>7} {'Pct':>7}")
    print(f"  {'-'*70} {'-'*7} {'-'*7}")
    for method, count in methods.most_common(30):
        print(f"  {method[:68]:<68} {count:>7d} {count/total*100:>6.1f}%")

    threads = analysis.cpu_thread_counts()
    print(f"\n  {'Thread Distribution':^80}")
    print(f"  {'Thread':<50} {'Count':>7} {'Pct':>7}")
    print(f"  {'-'*50} {'-'*7} {'-'*7}")
    for t, c in threads.most_common(15):
        print(f"  {t[:48]:<48} {c:>7d} {c/total*100:>6.1f}%")

    print_header("TOP CPU STACK SIGNATURES (top 5 frames)")
    sigs = analysis.cpu_stack_sigs(depth=5)
    for sig, count in sigs.most_common(20):
        print(f"\n  [{count}x, {count/total*100:.1f}%]")
        for line in sig.split(" -> "):
            print(f"    {line}")

    # ── Section 3: Allocation Hotspots ───────────────────────────────────
    print_header("MEMORY ALLOCATION HOTSPOTS")
    alloc = analysis.alloc_by_class()
    total_alloc = sum(alloc.values()) or 1
    print(f"\n  Total allocation: {format_bytes(total_alloc)}")
    print(f"  Sample count: {analysis.alloc_sample_count}")

    print(f"\n  {'Top 40 Allocation Types':^80}")
    print(f"  {'Type':<55} {'Bytes':>14} {'Pct':>7}")
    print(f"  {'-'*55} {'-'*14} {'-'*7}")
    for cls, w in alloc.most_common(40):
        print(f"  {cls[:53]:<53} {w:>14,d} {w/total_alloc*100:>6.1f}%")

    print_header("TOP byte[] ALLOCATION SITES")
    byte_stacks = analysis.alloc_stack_sigs(class_filter="[B", depth=4)
    total_byte = sum(byte_stacks.values()) or 1
    print(f"\n  Total byte[]: {format_bytes(total_byte)}")
    for sig, w in byte_stacks.most_common(20):
        print(f"\n  {w:>12,d} ({w/total_byte*100:.1f}%)")
        for line in sig.split(" -> "):
            print(f"    {line}")

    # ── Section 4: GC / Heap Timeline ────────────────────────────────────
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
    else:
        print("\n  No GCHeapSummary events found.")

    # ── Section 5: GC Pause Times ────────────────────────────────────────
    print_header("GC PAUSE TIMES")
    stats = analysis.gc_pause_stats()
    print(f"\n  Pause count: {stats['count']}")
    print(f"  Total pause time: {stats['total_ms']:,.1f} ms")
    print(f"  Avg pause: {stats['avg_ms']:,.2f} ms   Max pause: {stats['max_ms']:,.2f} ms")
    if analysis.recording_duration_s() > 0:
        pct_run = stats['total_ms'] / 1000 / analysis.recording_duration_s() * 100
        print(f"  Pause time as % of recording: {pct_run:.2f}%")
    by_phase = analysis.gc_pause_by_phase()
    if by_phase:
        print(f"\n  {'By Phase':^60}")
        print(f"  {'Phase':<40} {'Total (ms)':>15}")
        print(f"  {'-'*40} {'-'*15}")
        for phase, ms in by_phase.most_common(15):
            print(f"  {phase[:38]:<38} {ms:>15,.1f}")

    # ── Section 6: Class Loading ─────────────────────────────────────────
    print_header("CLASS LOADING")
    loaded, unloaded = analysis.class_loading_final()
    print(f"\n  Classes loaded (final):   {loaded:,}")
    print(f"  Classes unloaded (final): {unloaded:,}")
    series = analysis.class_loading_series()
    if series:
        print(f"\n  {'Timestamp':<22} {'Loaded classes':>16}")
        print(f"  {'-'*22} {'-'*16}")
        for ts, n in series[-15:]:
            print(f"  {ts:<22} {n:>16,d}")

    # ── Section 7: Thread Creation ───────────────────────────────────────
    print_header("THREAD CREATION")
    print(f"\n  Threads started: {analysis.thread_start_count:,}")
    print(f"  Threads ended:   {analysis.thread_end_count:,}")
    pools = analysis.thread_pool_breakdown()
    if pools:
        print(f"\n  {'Grouped by pool / name prefix':^70}")
        print(f"  {'Pool / prefix':<50} {'Started':>10}")
        print(f"  {'-'*50} {'-'*10}")
        for name, count in pools.most_common(25):
            print(f"  {name[:48]:<48} {count:>10,d}")

    # ── Section 8: Lock Contention ───────────────────────────────────────
    print_header("LOCK CONTENTION")
    print(f"\n  Monitor enter events: {len(analysis.monitor_enter_events):,}   "
          f"total wait: {analysis.monitor_contention_total_ms:,.1f} ms")
    top_mon = analysis.monitor_contention_top(20)
    if top_mon:
        print(f"\n  {'Top Contended Monitor Classes':^80}")
        print(f"  {'Class':<50} {'Wait (ms)':>13} {'Events':>10}")
        print(f"  {'-'*50} {'-'*13} {'-'*10}")
        for cls, ms, cnt in top_mon:
            print(f"  {cls[:48]:<48} {ms:>13,.1f} {cnt:>10,d}")

    print(f"\n  Thread park events: {len(analysis.thread_park_events):,}   "
          f"total park time: {analysis.thread_park_total_ms:,.1f} ms")
    top_park = analysis.thread_park_top(20)
    if top_park:
        print(f"\n  {'Top Parked Classes':^80}")
        print(f"  {'Class':<50} {'Park time (ms)':>16} {'Events':>10}")
        print(f"  {'-'*50} {'-'*16} {'-'*10}")
        for cls, ms, cnt in top_park:
            print(f"  {cls[:48]:<48} {ms:>16,.1f} {cnt:>10,d}")

    # ── Section 9: JIT Compilation ───────────────────────────────────────
    print_header("JIT COMPILATION")
    print(f"\n  Compilations: {analysis.compilation_count:,}")
    print(f"  Total compile time: {analysis.compilation_total_ms:,.1f} ms")
    if analysis.recording_duration_s() > 0:
        pct_run = analysis.compilation_total_ms / 1000 / analysis.recording_duration_s() * 100
        print(f"  Compile time as % of recording: {pct_run:.2f}%")
    top_compiled = analysis.compilation_top_methods(20)
    if top_compiled:
        print(f"\n  {'Top Compiled Methods by Time':^90}")
        print(f"  {'Method':<60} {'Level':>6} {'Time (ms)':>14}")
        print(f"  {'-'*60} {'-'*6} {'-'*14}")
        for ms, method, level in top_compiled:
            print(f"  {method[:58]:<58} {str(level):>6} {ms:>14,.2f}")

    # ── Section 10: I/O Activity ─────────────────────────────────────────
    print_header("SOCKET / FILE I/O ACTIVITY")
    sock = analysis.io_socket_summary()
    print(f"\n  Sockets — reads: {sock['read_count']:,} ({format_bytes(sock['read_bytes'])}, "
          f"{sock['read_ms']:,.1f} ms wait)")
    print(f"  Sockets — writes: {sock['write_count']:,} ({format_bytes(sock['write_bytes'])}, "
          f"{sock['write_ms']:,.1f} ms wait)")
    top_hosts = analysis.io_socket_top_hosts()
    if top_hosts:
        print(f"\n  {'Top Hosts by I/O Wait Time':^70}")
        print(f"  {'Host':<45} {'Wait (ms)':>15}")
        print(f"  {'-'*45} {'-'*15}")
        for host, ms in top_hosts:
            print(f"  {host[:43]:<43} {ms:>15,.1f}")

    fio = analysis.io_file_summary()
    print(f"\n  Files — reads: {fio['read_count']:,} ({format_bytes(fio['read_bytes'])}, "
          f"{fio['read_ms']:,.1f} ms wait)")
    print(f"  Files — writes: {fio['write_count']:,} ({format_bytes(fio['write_bytes'])}, "
          f"{fio['write_ms']:,.1f} ms wait)")
    top_paths = analysis.io_file_top_paths()
    if top_paths:
        print(f"\n  {'Top Paths by I/O Wait Time':^90}")
        print(f"  {'Path':<65} {'Wait (ms)':>15}")
        print(f"  {'-'*65} {'-'*15}")
        for path, ms in top_paths:
            print(f"  {path[:63]:<63} {ms:>15,.1f}")

    # ── Section 11: CPU Load Timeline ────────────────────────────────────
    print_header("CPU LOAD TIMELINE")
    avg_user, avg_sys, avg_machine = analysis.cpu_load_avg()
    print(f"\n  Avg JVM user: {avg_user:.1f}%   Avg JVM system: {avg_sys:.1f}%   Avg machine total: {avg_machine:.1f}%")
    cpu_series = analysis.cpu_load_series()
    if cpu_series:
        print(f"\n  {'Timestamp':<22} {'JVM User':>9} {'JVM Sys':>9} {'Machine':>9}")
        print(f"  {'-'*22} {'-'*9} {'-'*9} {'-'*9}")
        for ts, u, s, m in cpu_series[-20:]:
            print(f"  {ts:<22} {u:>8.1f}% {s:>8.1f}% {m:>8.1f}%")

    # ── Section 12: Wall Clock Sleeping ──────────────────────────────────
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

    Compares all sections from report_single():
    1.  Allocation types — with ELIMINATED/NEW markers
    2.  CPU hot methods + thread distribution
    3.  GC heap + pause times by phase
    4.  Class loading totals
    5.  Thread creation by pool
    6.  Lock contention — monitor enter + thread park
    7.  JIT compilation
    8.  Socket / file I/O
    9.  CPU load averages
    10. Wall clock sleeping
    11. Overall summary — key metrics at a glance
    """
    print_header("BEFORE vs AFTER COMPARISON")
    print(f"  Before: {before.name}  ({before.recording_duration_s():.3f}s, JVM {before.jvm_version()})")
    print(f"  After:  {after.name}  ({after.recording_duration_s():.3f}s, JVM {after.jvm_version()})")

    # ── Section 1: Allocation Comparison ─────────────────────────────────
    print_header("ALLOCATION COMPARISON")
    old_alloc = before.alloc_by_class()
    new_alloc = after.alloc_by_class()
    old_total = sum(old_alloc.values())
    new_total = sum(new_alloc.values())

    print(f"\n  {'Metric':<48} {'Before':>15} {'After':>15} {'Change':>15}")
    print(f"  {'-'*48} {'-'*15} {'-'*15} {'-'*15}")
    print(f"  {'Total allocation':<48} {format_bytes(old_total):>15} {format_bytes(new_total):>15} {format_bytes(new_total-old_total):>15}")
    print(f"  {'Allocation samples':<48} {before.alloc_sample_count:>15,d} {after.alloc_sample_count:>15,d} {after.alloc_sample_count-before.alloc_sample_count:>+15,d}")

    print(f"\n  {'Top Allocation Types Comparison':^95}")
    print(f"  {'Type':<52} {'Before':>13} {'After':>13} {'Delta':>14}")
    print(f"  {'-'*52} {'-'*13} {'-'*13} {'-'*14}")
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
        print(f"  {t[:50]:<50} {o:>13,d} {n:>13,d} {delta:>+14,d} ({pct_change(o, n)}){marker}")

    # ── Section 2: CPU Comparison ────────────────────────────────────────
    print_header("CPU EXECUTION SAMPLE COMPARISON")
    old_methods = before.cpu_method_counts()
    new_methods = after.cpu_method_counts()
    old_cpu_total = sum(old_methods.values())
    new_cpu_total = sum(new_methods.values())
    print(f"\n  Before: {int(old_cpu_total)} samples")
    print(f"  After:  {int(new_cpu_total)} samples")
    if old_cpu_total:
        print(f"  Delta:  {int(new_cpu_total - old_cpu_total):+d} ({pct_change(old_cpu_total, new_cpu_total)})")

    print(f"\n  {'Top Hot Methods Comparison':^90}")
    print(f"  {'Method':<65} {'Before':>8} {'After':>8} {'Delta':>8}")
    print(f"  {'-'*65} {'-'*8} {'-'*8} {'-'*8}")
    all_methods = set(old_methods) | set(new_methods)
    for m in sorted(all_methods, key=lambda m: old_methods.get(m, 0), reverse=True)[:30]:
        o, n = old_methods.get(m, 0), new_methods.get(m, 0)
        delta = n - o
        marker = " ◀◀" if (o > 2 and n == 0) or (o >= 5 and delta <= -o * 0.5) else ""
        print(f"  {m[:63]:<63} {o:>8} {n:>8} {delta:>+8}{marker}")

    print(f"\n  {'Thread Distribution Comparison':^90}")
    print(f"  {'Thread':<40} {'Before':>8} {'After':>8} {'Delta':>8}")
    print(f"  {'-'*40} {'-'*8} {'-'*8} {'-'*8}")
    old_threads = before.cpu_thread_counts()
    new_threads = after.cpu_thread_counts()
    all_threads = set(old_threads) | set(new_threads)
    for t in sorted(all_threads, key=lambda t: old_threads.get(t, 0), reverse=True)[:15]:
        o, n = old_threads.get(t, 0), new_threads.get(t, 0)
        print(f"  {t[:38]:<38} {o:>8} {n:>8} {n-o:>+8}")

    # ── Section 3: GC Heap Comparison ────────────────────────────────────
    print_header("GC / HEAP COMPARISON")
    old_heap = before.gc_heap_series()
    new_heap = after.gc_heap_series()
    if old_heap:
        print(f"\n  Before: {len(old_heap)} GC events, "
              f"heap {min(h[1] for h in old_heap):.1f} → {max(h[1] for h in old_heap):.1f} MB")
    else:
        print("\n  Before: no GC data")
    if new_heap:
        print(f"  After:  {len(new_heap)} GC events, "
              f"heap {min(h[1] for h in new_heap):.1f} → {max(h[1] for h in new_heap):.1f} MB")
    else:
        print("  After:  no GC data")
    if old_heap and new_heap:
        print(f"  GC event count change: {len(new_heap) - len(old_heap):+d} ({pct_change(len(old_heap), len(new_heap))})")

    # ── Section 4: GC Pause Time Comparison ──────────────────────────────
    print_header("GC PAUSE TIME COMPARISON")
    ob = before.gc_pause_stats()
    oa = after.gc_pause_stats()
    print(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    print(f"  {'-'*30} {'-'*15} {'-'*15} {'-'*15}")
    print(f"  {'Pause count':<30} {ob['count']:>15,d} {oa['count']:>15,d} {oa['count']-ob['count']:>+15,d}")
    print(f"  {'Total pause (ms)':<30} {ob['total_ms']:>15,.1f} {oa['total_ms']:>15,.1f} {oa['total_ms']-ob['total_ms']:>+15,.1f}")
    print(f"  {'Avg pause (ms)':<30} {ob['avg_ms']:>15,.2f} {oa['avg_ms']:>15,.2f} {oa['avg_ms']-ob['avg_ms']:>+15,.2f}")
    print(f"  {'Max pause (ms)':<30} {ob['max_ms']:>15,.2f} {oa['max_ms']:>15,.2f} {oa['max_ms']-ob['max_ms']:>+15,.2f}")

    old_phase = before.gc_pause_by_phase()
    new_phase = after.gc_pause_by_phase()
    all_phases = set(old_phase) | set(new_phase)
    if all_phases:
        print(f"\n  {'By Phase (ms)':^70}")
        print(f"  {'Phase':<35} {'Before':>12} {'After':>12} {'Delta':>12}")
        print(f"  {'-'*35} {'-'*12} {'-'*12} {'-'*12}")
        for phase in sorted(all_phases, key=lambda p: old_phase.get(p, 0), reverse=True):
            o, n = old_phase.get(phase, 0), new_phase.get(phase, 0)
            print(f"  {phase[:33]:<33} {o:>12,.1f} {n:>12,.1f} {n-o:>+12,.1f}")

    # ── Section 5: Class Loading Comparison ──────────────────────────────
    print_header("CLASS LOADING COMPARISON")
    ol, ou = before.class_loading_final()
    nl, nu = after.class_loading_final()
    print(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    print(f"  {'-'*30} {'-'*15} {'-'*15} {'-'*15}")
    print(f"  {'Classes loaded':<30} {ol:>15,d} {nl:>15,d} {nl-ol:>+15,d} ({pct_change(ol, nl)})")
    print(f"  {'Classes unloaded':<30} {ou:>15,d} {nu:>15,d} {nu-ou:>+15,d} ({pct_change(ou, nu)})")

    # ── Section 6: Thread Creation Comparison ────────────────────────────
    print_header("THREAD CREATION COMPARISON")
    print(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    print(f"  {'-'*30} {'-'*15} {'-'*15} {'-'*15}")
    print(f"  {'Threads started':<30} {before.thread_start_count:>15,d} {after.thread_start_count:>15,d} "
          f"{after.thread_start_count-before.thread_start_count:>+15,d} ({pct_change(before.thread_start_count, after.thread_start_count)})")
    print(f"  {'Threads ended':<30} {before.thread_end_count:>15,d} {after.thread_end_count:>15,d} "
          f"{after.thread_end_count-before.thread_end_count:>+15,d}")

    old_pools = before.thread_pool_breakdown()
    new_pools = after.thread_pool_breakdown()
    all_pools = set(old_pools) | set(new_pools)
    if all_pools:
        print(f"\n  {'By Pool / Name Prefix':^70}")
        print(f"  {'Pool / prefix':<40} {'Before':>10} {'After':>10} {'Delta':>10}")
        print(f"  {'-'*40} {'-'*10} {'-'*10} {'-'*10}")
        for p in sorted(all_pools, key=lambda p: old_pools.get(p, 0), reverse=True)[:25]:
            o, n = old_pools.get(p, 0), new_pools.get(p, 0)
            print(f"  {p[:38]:<38} {o:>10,d} {n:>10,d} {n-o:>+10,d}")

    # ── Section 7: Lock Contention Comparison ────────────────────────────
    print_header("LOCK CONTENTION COMPARISON")
    print(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    print(f"  {'-'*30} {'-'*15} {'-'*15} {'-'*15}")
    print(f"  {'Monitor enter events':<30} {len(before.monitor_enter_events):>15,d} {len(after.monitor_enter_events):>15,d} "
          f"{len(after.monitor_enter_events)-len(before.monitor_enter_events):>+15,d}")
    print(f"  {'Monitor wait time (ms)':<30} {before.monitor_contention_total_ms:>15,.1f} {after.monitor_contention_total_ms:>15,.1f} "
          f"{after.monitor_contention_total_ms-before.monitor_contention_total_ms:>+15,.1f}")
    print(f"  {'Thread park events':<30} {len(before.thread_park_events):>15,d} {len(after.thread_park_events):>15,d} "
          f"{len(after.thread_park_events)-len(before.thread_park_events):>+15,d}")
    print(f"  {'Park time (ms)':<30} {before.thread_park_total_ms:>15,.1f} {after.thread_park_total_ms:>15,.1f} "
          f"{after.thread_park_total_ms-before.thread_park_total_ms:>+15,.1f}")

    old_mon = dict((c, ms) for c, ms, _ in before.monitor_contention_top(100))
    new_mon = dict((c, ms) for c, ms, _ in after.monitor_contention_top(100))
    all_mon = set(old_mon) | set(new_mon)
    if all_mon:
        print(f"\n  {'Top Contended Monitor Classes (ms)':^80}")
        print(f"  {'Class':<45} {'Before':>13} {'After':>13} {'Delta':>13}")
        print(f"  {'-'*45} {'-'*13} {'-'*13} {'-'*13}")
        for cls in sorted(all_mon, key=lambda c: old_mon.get(c, 0), reverse=True)[:20]:
            o, n = old_mon.get(cls, 0), new_mon.get(cls, 0)
            marker = " ◀◀ ELIMINATED" if o > 0 and n == 0 else ""
            print(f"  {cls[:43]:<43} {o:>13,.1f} {n:>13,.1f} {n-o:>+13,.1f}{marker}")

    # ── Section 8: JIT Compilation Comparison ────────────────────────────
    print_header("JIT COMPILATION COMPARISON")
    print(f"\n  {'Metric':<30} {'Before':>15} {'After':>15} {'Change':>15}")
    print(f"  {'-'*30} {'-'*15} {'-'*15} {'-'*15}")
    print(f"  {'Compilations':<30} {before.compilation_count:>15,d} {after.compilation_count:>15,d} "
          f"{after.compilation_count-before.compilation_count:>+15,d} ({pct_change(before.compilation_count, after.compilation_count)})")
    print(f"  {'Total compile time (ms)':<30} {before.compilation_total_ms:>15,.1f} {after.compilation_total_ms:>15,.1f} "
          f"{after.compilation_total_ms-before.compilation_total_ms:>+15,.1f} ({pct_change(before.compilation_total_ms, after.compilation_total_ms)})")

    # ── Section 9: I/O Comparison ────────────────────────────────────────
    print_header("SOCKET / FILE I/O COMPARISON")
    os_ = before.io_socket_summary()
    ns_ = after.io_socket_summary()
    print(f"\n  {'Metric':<30} {'Before':>18} {'After':>18} {'Change':>15}")
    print(f"  {'-'*30} {'-'*18} {'-'*18} {'-'*15}")
    print(f"  {'Socket reads':<30} {os_['read_count']:>18,d} {ns_['read_count']:>18,d} {ns_['read_count']-os_['read_count']:>+15,d}")
    print(f"  {'Socket bytes read':<30} {format_bytes(os_['read_bytes']):>18} {format_bytes(ns_['read_bytes']):>18} {format_bytes(ns_['read_bytes']-os_['read_bytes']):>15}")
    print(f"  {'Socket writes':<30} {os_['write_count']:>18,d} {ns_['write_count']:>18,d} {ns_['write_count']-os_['write_count']:>+15,d}")
    print(f"  {'Socket bytes written':<30} {format_bytes(os_['write_bytes']):>18} {format_bytes(ns_['write_bytes']):>18} {format_bytes(ns_['write_bytes']-os_['write_bytes']):>15}")

    of_ = before.io_file_summary()
    nf_ = after.io_file_summary()
    print(f"\n  {'File reads':<30} {of_['read_count']:>18,d} {nf_['read_count']:>18,d} {nf_['read_count']-of_['read_count']:>+15,d}")
    print(f"  {'File bytes read':<30} {format_bytes(of_['read_bytes']):>18} {format_bytes(nf_['read_bytes']):>18} {format_bytes(nf_['read_bytes']-of_['read_bytes']):>15}")
    print(f"  {'File writes':<30} {of_['write_count']:>18,d} {nf_['write_count']:>18,d} {nf_['write_count']-of_['write_count']:>+15,d}")
    print(f"  {'File bytes written':<30} {format_bytes(of_['write_bytes']):>18} {format_bytes(nf_['write_bytes']):>18} {format_bytes(nf_['write_bytes']-of_['write_bytes']):>15}")

    # ── Section 10: CPU Load Comparison ──────────────────────────────────
    print_header("CPU LOAD COMPARISON")
    ou_, os2, om = before.cpu_load_avg()
    nu_, ns2, nm = after.cpu_load_avg()
    print(f"\n  {'Metric':<30} {'Before':>12} {'After':>12} {'Change':>12}")
    print(f"  {'-'*30} {'-'*12} {'-'*12} {'-'*12}")
    print(f"  {'Avg JVM user %':<30} {ou_:>11.1f}% {nu_:>11.1f}% {nu_-ou_:>+11.1f}%")
    print(f"  {'Avg JVM system %':<30} {os2:>11.1f}% {ns2:>11.1f}% {ns2-os2:>+11.1f}%")
    print(f"  {'Avg machine total %':<30} {om:>11.1f}% {nm:>11.1f}% {nm-om:>+11.1f}%")

    # ── Section 11: Sleep Comparison ─────────────────────────────────────
    print_header("WALL CLOCK SLEEPING COMPARISON")
    old_sleep = before.sleep_by_thread()
    new_sleep = after.sleep_by_thread()
    old_sleep_total = sum(old_sleep.values())
    new_sleep_total = sum(new_sleep.values())
    print(f"\n  Before: {len(before.sleep_events)} events, {old_sleep_total/1000:.1f}s total")
    print(f"  After:  {len(after.sleep_events)} events, {new_sleep_total/1000:.1f}s total")

    print(f"\n  {'Thread':<40} {'Before (ms)':>12} {'After (ms)':>12} {'Delta':>12}")
    print(f"  {'-'*40} {'-'*12} {'-'*12} {'-'*12}")
    all_sleep_threads = set(old_sleep) | set(new_sleep)
    for t in sorted(all_sleep_threads, key=lambda t: old_sleep.get(t, 0), reverse=True)[:15]:
        o, n = old_sleep.get(t, 0), new_sleep.get(t, 0)
        print(f"  {t[:38]:<38} {o:>12,.0f} {n:>12,.0f} {n-o:>+12,.0f}")

    # ── Section 12: Overall Summary ──────────────────────────────────────
    print_header("SUMMARY")
    dur_delta = after.recording_duration_s() - before.recording_duration_s()
    print(f"\n  Recording duration: {before.recording_duration_s():.3f}s → {after.recording_duration_s():.3f}s "
          f"({dur_delta:+.3f}s, {pct_change(before.recording_duration_s(), after.recording_duration_s())})")
    print(f"  Allocation: {format_bytes(old_total)} → {format_bytes(new_total)} ({pct_change(old_total, new_total)})")
    print(f"  GC pause time: {ob['total_ms']:,.1f} ms → {oa['total_ms']:,.1f} ms ({pct_change(ob['total_ms'], oa['total_ms'])})")
    print(f"  JIT compile time: {before.compilation_total_ms:,.1f} ms → {after.compilation_total_ms:,.1f} ms "
          f"({pct_change(before.compilation_total_ms, after.compilation_total_ms)})")
    print(f"  Classes loaded: {ol:,} → {nl:,} ({pct_change(ol, nl)})")
    print(f"  Threads started: {before.thread_start_count:,} → {after.thread_start_count:,} "
          f"({pct_change(before.thread_start_count, after.thread_start_count)})")
    print(f"  Lock wait time: {before.monitor_contention_total_ms:,.1f} ms → {after.monitor_contention_total_ms:,.1f} ms "
          f"({pct_change(before.monitor_contention_total_ms, after.monitor_contention_total_ms)})")
    print(f"  Wall clock sleep: {old_sleep_total/1000:.1f}s → {new_sleep_total/1000:.1f}s "
          f"({pct_change(old_sleep_total, new_sleep_total)})")


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
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    files = sys.argv[1:]

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
