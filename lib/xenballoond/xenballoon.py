#!/usr/bin/env python
""" Xen virtual machine ballooning backend module """

import os, re, subprocess, sys, time
import meta


# constants
NORMAL_MODE     = 1
FREEZE_MODE     = 2
EMERGENCY_MODE  = 3


class Xenballoon:
    mode                = NORMAL_MODE
    oom_safe_ratio      = 1
    xenstore_enabled    = True
    meminfo             = {}
    vmstat              = {}

    # path to standard commands
    os_sync             = "/bin/sync"

    # path to xenstore commands
    xs_exists           = "/usr/bin/xenstore-exists"
    xs_read             = "/usr/bin/xenstore-read"
    xs_write            = "/usr/bin/xenstore-write"

    # paths to files within procfs
    proc_loadavg        = "/proc/loadavg"
    proc_meminfo        = "/proc/meminfo"
    proc_stat           = "/proc/stat"
    proc_uptime         = "/proc/uptime"
    proc_vmstat         = "/proc/vmstat"
    proc_xen_balloon    = "/proc/xen/balloon"
    proc_drop_caches    = "/proc/sys/vm/drop_caches"


    #
    # __init__()
    # --------
    ## Initialisation
    # @param config     a ConfigParser instance
    def __init__(self, config):
        self.config  = config


    #
    # minmb()
    # -----
    # @return integer
    #
    def minmb(self):
        minmem = self.config.getint("xenballoond", "minmem")

        if minmem != 0:
            return minmem

        kb = int(open(self.config.get("xenballoond", "maxmem_file"), "r").read())
        mb = kb / 1024
        pages = kb / 4

        if mb < 2000:
            memMin = 104 + (pages >> 11)
        else:
            memMin = 296 + (pages >> 13)

        return memMin


    #
    # selftarget()
    # ----------
    # @return integer
    #
    def selftarget(self, action="getTarget"):
        if action == "getcurkb":
            return self.meminfo["MemTotal"]

        tgtkb = self.meminfo["Committed_AS"] * self.oom_safe_ratio

        if self.config.getboolean("xenballoond", "preserve_cache") \
            and self.mode != EMERGENCY_MODE:
            tgtkb = tgtkb + self.meminfo["Active"]

        minbytes = self.minmb() * 1024 * 1024
        tgtbytes = tgtkb * 1024

        if tgtbytes < minbytes:
            return minbytes
        else:
            return tgtbytes


    #
    # downhysteresis()
    # --------------
    # @return integer rate at which target memory is ballooned out
    #
    def downhysteresis(self):
        if self.xenstore_enabled:
            if subprocess.call([self.xs_exists, "memory/downhysteresis"]) == 0:
                dhs = int(subprocess.Popen([self.xs_read, "memory/downhysteresis"],
                    stdout=subprocess.PIPE).communicate()[0])
                return dhs

        return self.config.getint("xenballoond", "down_hysteresis")


    #
    # uphysteresis()
    # ------------
    # @return integer rate at which target memory is reclaimed
    #
    def uphysteresis(self):
        if self.xenstore_enabled:
            if subprocess.call([self.xs_exists, "memory/uphysteresis"]) == 0:
                uhs = int(subprocess.Popen([self.xs_read, "memory/uphysteresis"],
                    stdout=subprocess.PIPE).communicate()[0])
                return uhs

        return self.config.getint("xenballoond", "up_hysteresis")


    #
    # selfballoon()
    # -----------
    def selfballoon(self):
        if self.xenstore_enabled:
            if subprocess.call([self.xs_exists, "memory/selfballoon"]) == 0:
                if int(subprocess.Popen([self.xs_read, "memory/selfballoon"],
                    stdout=subprocess.PIPE).communicate()[0]) == 1:
                    return True

        return self.config.getboolean("xenballoond", "selfballoon_enabled")


    #
    # balloon_to_target()
    # -----------------
    def balloon_to_target(self, target=None):
        if not target:
            tgtbytes = self.selftarget()
        else:
            tgtbytes = target * 1024

        curbytes = self.selftarget("getcurkb") * 1024

        if self.mode != EMERGENCY_MODE:
            if curbytes > tgtbytes:
                downhys = self.downhysteresis()
                if downhys != 0:
                    tgtbytes = curbytes - (curbytes - tgtbytes) / downhys
            elif curbytes < tgtbytes:
                uphys = self.uphysteresis()
                tgtbytes = curbytes + (tgtbytes - curbytes) / uphys

        open(self.proc_xen_balloon, "w").write(str(tgtbytes))

        if self.xenstore_enabled:
            valstr = str(tgtbytes/1024)
            subprocess.call([self.xs_write, "memory/selftarget", valstr])


    #
    # fetch_memory_stats()
    # ------------------
    def fetch_memory_stats(self):
        input = open(self.proc_meminfo, "r")

        for line in input.readlines():
            val = re.match('([\w()]+):[ \t]*([0-9]+).*', line)
            self.meminfo[val.group(1)] = int(val.group(2))

        input.close()
        input = open(self.proc_vmstat, "r")

        for line in input.readlines():
            val = re.match('([\w()]+)[ \t]+([0-9]+).*', line)
            self.vmstat[val.group(1)] = int(val.group(2))

        input.close()


    #
    # send_memory_stats()
    # -----------------
    def send_memory_stats(self):
        if not self.xenstore_enabled:
            return

        if self.config.getboolean("xenballoond", "send_meminfo") \
            and subprocess.call([self.xs_exists, "stats/meminfo"]) == 0:
            subprocess.call([self.xs_write, "stats/meminfo", str(self.meminfo)])

        if self.config.getboolean("xenballoond", "send_vmstat") \
            and subprocess.call([self.xs_exists, "stats/vmstat"]) == 0:
            subprocess.call([self.xs_write, "stats/vmstat", str(self.vmstat)])

        if self.config.getboolean("xenballoond", "send_uptime") \
            and subprocess.call([self.xs_exists, "stats/uptime"]) == 0:
            uptimes = open(self.proc_uptime, "r").read().split()
            uptime = { 'uptime': uptimes[0], 'idle': uptimes[1] }
            subprocess.call([self.xs_write, "stats/uptime", str(uptime)])


    #
    # send_cpu_stats()
    # --------------
    def send_cpu_stats(self):
        if self.config.getboolean("xenballoond", "send_cpustat") \
            and subprocess.call([self.xs_exists, "stats/system"]) == 0:
            param_lst = [ 'loadavg', 'loadavg5', 'loadavg10', 'run_proc',
                          'lastps', 'cpu', 'cpu_us', 'cpu_ni', 'cpu_sy',
                          'cpu_idle', 'cpu_wa', 'c1', 'c2', 'c3', 'c4' ]
            cpustat = {}
            lavg = open(self.proc_loadavg, "r").readline()
            cpust = open(self.proc_stat, "r").readline()
            full_stat = lavg.split() + cpust.split()

            for n in range(0, len(full_stat)):
                cpustat[param_lst[n]] = full_stat[n]

            subprocess.call([self.xs_write, "stats/system", str(cpustat)])


    #
    # init()
    # ----
    def init(self):
        # check the environment
        if not os.path.exists(self.proc_xen_balloon):
            sys.stderr.write(meta.name+": fatal: Balloon driver not installed\n")
            sys.exit(1)

        if not os.path.exists(self.proc_meminfo):
            sys.stderr.write(meta.name+": fatal: Can't read "+self.proc_meminfo+"\n")
            sys.exit(1)

        if os.path.exists(self.xs_exists) and os.path.exists(self.xs_read) \
            and os.path.exists(self.xs_write):
            self.xenstore_enabled = True
        else:
            self.xenstore_enabled = False
            sys.stderr.write(meta.name+": error: Missing /usr/bin/xenstore-* " \
                "tools, disabling directed ballooning\n")

        # calculate the OOM safe ratio
        try:
            minmem_reserve = self.config.getint("xenballoond", "minmem_reserve")
            self.oom_safe_ratio = float(100 + minmem_reserve) / 100
        except NameError:
            sys.stderr.write(meta.name+": error: Missing 'minmem_reserve' " \
                "option in config file, disabling oom_safe\n")


    #
    # run()
    # ---
    def run(self):
        config  = self.config
        interval= config.getint("xenballoond", "selfballoon_interval")

        while True:
            # fetch memory statistics
            self.fetch_memory_stats()

            # update the memory peak
            maxmem_file = config.get("xenballoond", "maxmem_file")
            maxkb = int(open(maxmem_file, "r").read())
            curkb = self.selftarget("getcurkb")

            if curkb > maxkb:
                open(maxmem_file, "w").write(str(curkb))

            # read the memory allocation mode
            if subprocess.call([self.xs_exists, "memory/mode"]) == 0:
                self.mode = int(subprocess.Popen([self.xs_read, "memory/mode"],
                            stdout=subprocess.PIPE).communicate()[0])

            # handle the memory according to the current mode
            if self.mode == NORMAL_MODE:
                if self.selfballoon():
                    self.balloon_to_target()
                    interval = config.getint("xenballoond", "selfballoon_interval")
                elif self.xenstore_enabled:
                    tgtkb = int(subprocess.Popen([self.xs_read, "memory/target"],
                            stdout=subprocess.PIPE).communicate()[0])
                    self.balloon_to_target(tgtkb)
                    interval = config.getint("xenballoond", "default_interval")

            elif self.mode == EMERGENCY_MODE:
                # we are requested to reclaim memory
                # 1. sync(8) data on disk
                subprocess.call([self.os_sync])
                # 2. free pagecache, dentries and inodes
                open(self.proc_drop_caches, "w").write("3")
                # 3. shrink down the memory
                self.balloon_to_target()

            else: # FREEZE_MODE
                pass

            # fetch and send statistics to the Xen host
            self.fetch_memory_stats()
            self.send_memory_stats()
            self.send_cpu_stats()

            # sleep before next iteration
            time.sleep(interval)

