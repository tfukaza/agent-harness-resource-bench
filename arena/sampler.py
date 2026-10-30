"""Process-tree sampler: memory, CPU, threads, file descriptors and disk for one trial."""
import pathlib, time
import psutil


def disk(path: pathlib.Path):
    files = size = 0
    for p in path.rglob('*'):
        try:
            if p.is_file():
                files += 1
                size += p.stat().st_size
        except OSError:
            pass
    return files, size


class Sampler:
    def __init__(self, pid: int, directory: pathlib.Path, uss: bool = False):
        self.pid = pid
        self.directory = directory
        self.want_uss = uss
        self.samples = []
        self.cpu = {}            # (pid, create_time) -> cumulative user+sys seconds
        self.cpu_by_phase = {}   # phase -> seconds attributed while that phase was current
        self.last_cpu_total = 0.0
        self.peak_disk = 0
        self.max = {'processes': 0, 'threads': 0, 'fds': 0, 'rss': 0, 'uss': 0}
        # Host-wide state, so a report can tell a quiet run from one taken on a loaded machine.
        self.swap_start = psutil.swap_memory()
        self.host = {'min_available': None, 'max_swap_used': 0}
        self.start = time.monotonic()

    def processes(self):
        try:
            root = psutil.Process(self.pid)
            return [root] + root.children(recursive=True)
        except psutil.Error:
            return []

    def sample(self, phase: str, turn, history_bytes: int):
        rss = uss = threads = fds = count = 0
        uss_ok = self.want_uss
        for p in self.processes():
            try:
                with p.oneshot():
                    rss += p.memory_info().rss
                    count += 1
                    t = p.cpu_times()
                    self.cpu[(p.pid, p.create_time())] = t.user + t.system
                    try:
                        threads += p.num_threads()
                    except psutil.Error:
                        pass
                    try:
                        fds += p.num_fds()
                    except (psutil.Error, AttributeError):
                        pass
                    if uss_ok:
                        try:
                            uss += p.memory_full_info().uss
                        except (psutil.Error, AttributeError):
                            uss_ok = False
            except psutil.Error:
                pass
        total_cpu = sum(self.cpu.values())
        self.cpu_by_phase[phase] = self.cpu_by_phase.get(phase, 0.0) + max(0.0, total_cpu - self.last_cpu_total)
        self.last_cpu_total = total_cpu
        host_available = psutil.virtual_memory().available
        host_swap_used = psutil.swap_memory().used
        self.host['min_available'] = host_available if self.host['min_available'] is None else min(self.host['min_available'], host_available)
        self.host['max_swap_used'] = max(self.host['max_swap_used'], host_swap_used)
        s = {'elapsed': time.monotonic() - self.start, 'rss': rss, 'processes': count, 'threads': threads, 'fds': fds,
             'phase': phase, 'turn': turn, 'history_bytes': history_bytes,
             'host_available': host_available, 'host_swap_used': host_swap_used}
        if uss_ok:
            s['uss'] = uss
        self.samples.append(s)
        for key, value in (('processes', count), ('threads', threads), ('fds', fds), ('rss', rss), ('uss', uss if uss_ok else 0)):
            self.max[key] = max(self.max[key], value)
        if len(self.samples) % 10 == 0:
            self.peak_disk = max(self.peak_disk, disk(self.directory)[1])
        return rss

    def summary(self):
        files, size = disk(self.directory)
        swap_end = psutil.swap_memory()
        pageouts = (swap_end.sout - self.swap_start.sout) if hasattr(swap_end, 'sout') else None
        return {
            'host_min_available_mib': (self.host['min_available'] / 1024 ** 2) if self.host['min_available'] is not None else None,
            'host_max_swap_used_mib': self.host['max_swap_used'] / 1024 ** 2,
            'host_pageouts': pageouts,
            'cpu_seconds_sampled': sum(self.cpu.values()),
            'cpu_by_phase': self.cpu_by_phase,
            'peak_rss_mib': self.max['rss'] / 1024 ** 2,
            'peak_uss_mib': (self.max['uss'] / 1024 ** 2) if self.want_uss and self.max['uss'] else None,
            'max_processes': self.max['processes'], 'max_threads': self.max['threads'], 'max_fds': self.max['fds'],
            'files': files, 'retained_bytes': size, 'peak_directory_bytes_sampled': max(self.peak_disk, size),
        }
