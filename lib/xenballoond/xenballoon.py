#!/usr/bin/env python
""" Xen virtual machine ballooning backend module """

import os, re, subprocess, sys, syslog, time


class Xenballoon:
    oom_safe_ratio      = 1
    xenstore_enabled    = True
    xs_exists           = "/usr/bin/xenstore-exists"
    xs_read             = "/usr/bin/xenstore-read"
    xs_write            = "/usr/bin/xenstore-write"


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
        meminfo = open("/proc/meminfo", "r").read()
        memTot = re.search('MemTotal:[ \t]*([0-9]*)', meminfo).group(1)

        if action == "getcurkb":
            return memTot

        tgtkb = int(re.search('Committed_AS:[ \t]*([0-9]*)', meminfo).group(1)) \
            * self.oom_safe_ratio

        if self.config.getboolean("xenballoond", "preserve_cache"):
            active_cache = int(re.search('Active:[ \t]*([0-9]*)', meminfo).group(1))
            tgtkb = tgtkb + active_cache

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

        open("/proc/xen/balloon", "w").write(str(tgtbytes))

        if self.xenstore_enabled:
            subprocess.call([self.xs_write, "memory/selftarget",
                str(int(tgtbytes)/1024)])


    #
    # send_memory_stats()
    # -----------------
    def send_memory_stats(self):
        if not self.xenstore_enabled:
            return

        if self.config.getboolean("xenballoond", "send_meminfo"):
            memI = {}
            meminfo = open("/proc/meminfo", "r")

            for line in meminfo.readlines():
                val = re.match('([\w()]*):[ \t]*([0-9]*).*', line)
                memI[val.group(1)] = val.group(2)

            meminfo.close()
            subprocess.call([self.xs_write, "memory/meminfo", str(memI)])

        if self.config.getboolean("xenballoond", "send_vmstat"):
            vmst = {}
            vmstat = open("/proc/vmstat", "r")

            for line in vmstat.readlines():
                val = re.match('([\w()]*)[ \t]*([0-9]*).*', line)
                vmst[val.group(1)] = val.group(2)

            vmstat.close()
            subprocess.call([self.xs_write, "memory/vmstat", str(vmst)])

        if self.config.getboolean("xenballoond", "send_uptime"):
            uptime = open("/proc/uptime", "r").read()
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
            lavg = open("/proc/loadavg", "r").readline()
            cpust = open("/proc/stat", "r").readline()
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
        if not os.path.exists("/proc/xen/balloon"):
            sys.stderr.write(__program__+": fatal: Balloon driver not installed\n")
            sys.exit(1)

        if not os.path.exists("/proc/meminfo"):
            sys.stderr.write(__program__+": fatal: Can't read /proc/meminfo\n")
            sys.exit(1)

        if os.path.exists(self.xs_exists) and os.path.exists(self.xs_read) \
            and os.path.exists(self.xs_write):
            self.xenstore_enabled = True
        else:
            self.xenstore_enabled = False
            sys.stderr.write(__program__+": error: Missing /usr/bin/xenstore-* " \
                "tools, disabling directed ballooning\n")

        # calculate the OOM safe ratio
        try:
            minmem_reserve = self.config.getint("xenballoond", "minmem_reserve")
            self.oom_safe_ratio = float(100 + minmem_reserve) / 100
        except NameError:
            sys.stderr.write(__program__+": error: Missing 'minmem_reserve' " \
                "option in config file, disabling oom_safe\n")


    #
    # run()
    # ---
    def run(self):
        while True:
            maxmem_file = self.config.get("xenballoond", "maxmem_file")
            maxkb = open(maxmem_file, "r").read()
            curkb = self.selftarget("getcurkb")

            if curkb > maxkb:
                open(maxmem_file, "w").write(str(curkb))

            if self.selfballoon():
                self.balloon_to_target()
                interval = self.config.getint("xenballoond", "selfballoon_interval")
            elif self.xenstore_enabled:
                tgtkb = int(subprocess.Popen([self.xs_read, "memory/target"],
                        stdout=subprocess.PIPE).communicate()[0])
                self.balloon_to_target(tgtkb)
                interval = self.config.getint("xenballoond", "default_interval")

            self.send_memory_stats()
            self.send_cpu_stats()
            time.sleep(interval)

