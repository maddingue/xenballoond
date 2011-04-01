#!/usr/bin/env python
""" Xen virtual machine ballooning backend module """

import os, re, subprocess, sys, syslog, time
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
    def minmb(self):
        minmem = self.config.getint("xenballoond", "minmem")

        if minmem != 0:
            return minmem

        kb = open(self.config.get("xenballoond", "maxmem_file"), "r").read()
        mb = int(kb) / 1024
        pages = int(kb) / 4

        if mb < 2000:
            memMin = 104 + (pages >> 11)
        else:
            memMin = 296 + (pages >> 13)

        return memMin


    #
    # selftarget()
    # ----------
    def selftarget(self, action="getTarget"):
        if action == "getcurkb":
            return self.meminfo["MemTotal"]

        tgtkb = self.meminfo["Committed_AS"] * self.oom_safe_ratio

        if self.config.getboolean("xenballoond", "preserve_cache"):
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

        curbytes = int(self.selftarget("getcurkb")) * 1024

        if curbytes > tgtbytes:
            downhys = self.downhysteresis()
            if downhys != 0:
                tgtbytes = curbytes - (curbytes - tgtbytes) / downhys
        elif curbytes < tgtbytes:
            uphys = self.uphysteresis()
            tgtbytes = curbytes + (tgtbytes - curbytes) / uphys

        open(self.proc_xen_balloon, "w").write(str(tgtbytes))

        if self.xenstore_enabled:
            subprocess.call([self.xs_write, "memory/selftarget",
                str(int(tgtbytes)/1024)])


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

        if self.config.getboolean("xenballoond", "send_meminfo"):
            subprocess.call([self.xs_write, "memory/meminfo", str(self.meminfo)])

        if self.config.getboolean("xenballoond", "send_vmstat"):
            subprocess.call([self.xs_write, "memory/vmstat", str(self.vmstat)])

        if self.config.getboolean("xenballoond", "send_uptime"):
            uptime = open(self.proc_uptime, "r").read()
            subprocess.call([self.xs_write, "memory/uptime", str(uptime)])


    #
    # send_cpu_stats()
    # --------------
    def send_cpu_stats(self):
        if self.config.getboolean("xenballoond", "send_cpustat"):
            param_lst = [ 'loadavg', 'loadavg5', 'loadavg10', 'run_proc',
                          'lastps', 'cpu', 'cpu_us', 'cpu_ni', 'cpu_sy',
                          'cpu_idle', 'cpu_wa', 'c1', 'c2', 'c3', 'c4' ]
            cpustat = {}
            lavg = open(self.proc_loadavg, "r").readline()
            cpust = open(self.proc_stat, "r").readline()
            full_stat = lavg.split() + cpust.split()

            for n in range(0, len(full_stat)):
                cpustat[param_lst[n]] = full_stat[n]

            if subprocess.call([self.xs_exists, "cpu_stats"]) == 0:
                subprocess.call([self.xs_write, "cpu_stats", str(cpustat)])


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
        mode    = self.mode

        while True:
            self.fetch_memory_stats()

            maxmem_file = config.get("xenballoond", "maxmem_file")
            maxkb = open(maxmem_file, "r").read()
            curkb = self.selftarget("getcurkb")

            if curkb > maxkb:
                open(maxmem_file, "w").write(str(curkb))

            if mode == NORMAL_MODE:
                if self.selfballoon():
                    self.balloon_to_target()
                    interval = config.getint("xenballoond", "selfballoon_interval")
                elif self.xenstore_enabled:
                    tgtkb = int(subprocess.Popen([self.xs_read, "memory/target"],
                            stdout=subprocess.PIPE).communicate()[0])
                    self.balloon_to_target(tgtkb)
                    interval = config.getint("xenballoond", "default_interval")

            elif mode == EMERGENCY_MODE:
                pass

            else: # FREEZE_MODE
                pass

            self.send_memory_stats()
            self.send_cpu_stats()
            time.sleep(interval)

