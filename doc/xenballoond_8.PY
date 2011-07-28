#!/usr/bin/env python
import os.path, subprocess, sys
sys.path += ["lib", "../lib"]
from xenballoond import meta

default_config  = "/etc/xen/"+meta.name+".conf"
default_pidfile = "/var/run/"+meta.name+".pid"

input = """
=head1 NAME

""" + meta.name + " - " + meta.description + """


=head1 VERSION

This is the manual page of """+meta.name+" version "+meta.version+"""


=head1 SYNOPSIS

    """+meta.name+" [--config "+default_config+"""]
                [--[no]detach]  [--pidfile """+default_pidfile+"""]

    """+meta.name+""" --help
    """+meta.name+""" --version


=head1 OPTIONS

B<Daemon options>

=over

=item B<-c>, B<--config> I<path>

Specify an alternate path to the configuration file.
Default path is F<""" + default_config + """>.

=item B<-D>, B<--[no]detach>

When specified, the program acts as a daemon, detaching itself from the
current terminal. Activated by default.

Specify B<--nodetach> to keep the program attached to the terminal.

=item B<-p>, B<--pidfile> I<path>

Specify the path to the PID file.
Defaults to F<""" + default_pidfile + """>.

=back

B<Standard options>

=over

=item B<-h>, B<--help>

Print this help screen and exit.

=item B<-V>, B<---version>

Print the program name and version and exit.

=back


=head1 DESCRIPTION

B<"""+meta.name+"""> is a daemon for managing the memory of a Xen domain
(a virtual machine) [...]

The sources for this program are available from
L<https://github.com/maddingue/xenballoond>


=head1 XENSTORE PATHS

These are the XenStore paths used by B<"""+meta.name+""">. The letter
after the path indicates whether the daemon reads (R) or writes (W) to
this path.

=over

=item *

C<memory/downhysteresis> (R) - rate (integer) at which target memory is
ballooned out

=item *

C<memory/mode> (R) - memory allocation mode;
available values: 1 (normal), 2 (freeze), 3 (emergency)

=item *

C<memory/selfballoon> (R) - enable (1) or disable (0) self-ballooning

=item *

C<memory/selftarget> (W)

=item *

C<memory/target> (R)

=item *

C<memory/uphysteresis> (R) - rate (integer) at which target memory is
reclaimed

=item *

C<stats/meminfo> (W) - parsed content from F</proc/meminfo>

=item *

C<stats/system> (W) - parsed content from F</proc/loadavg> and F</proc/stat>

=item *

C<stats/uptime> (W) - content of F</proc/uptime>

=item *

C<stats/vmstat> (W) - parsed content from F</proc/vmstat>

=back


=head1 CONFIGURATION

The configuration file is expected to use the C<.INI> format, with
the following sections and parameters.

=head2 Section [xenballoond]

=over

=item *

C<selfballoon_enabled> I<(boolean)> -
If selfballoon is true, selfballooning will occur, meaning the balloon
driver will grow and shrink according to available memory. If xenbus
is enabled, may be overridden by setting C<{memory/selfballoon}> to 0.
If false but xenballoond is able to communicate with domain0 via xenbus,
balloon targets will be set by domain0.

=item *

C<selfballoon_interval> I<(ineger)> -
If self-ballooning, number of seconds between checks/adjustments.
If xenbus is enabled, may be overridden by C<{memory/interval}>.

=item *

C<default_interval> I<(integer)> -
If B<not> self-ballooning but xenbus is enabled, number of seconds
between checks/adjustments. May be overridden by C<{memory/interval}>.

=item *

C<down_hysteresis> I<(integer)> -
When current > target, reduces rate at which target memory is ballooned
out. For a value of I<n>, I<1/n> of the difference will be ballooned.
This value applies both to selfballooning and directed ballooning.
May be overridden by C<{memory/downhysteresis}>.

=item *

C<up_hysteresis> I<(integer)> -
When current < target, reduces rate at which target memory is reclaimed
(if available). For a value of I<n>, I<1/n> of the difference will
be ballooned. This value applies both to selfballooning and directed
ballooning. May be overridden by C<{memory/uphysteresis}>.

=item *

C<minmem> I<(integer)> -
In order to avoid ballooning so much memory that a guest experiences
out-of-memory errors (OOMs), memory will not be ballooned out below
a minimum target, in MB. If this value is 0 (default), an heuristic
based on the maximum amount of memory will be used. (The heuristic
provides the same minimum as recent versions of the balloon driver but
early versions of the balloon driver did not enforce a minimum.)

=item *

C<minmem_istarget> I<(boolean)> -
If C<minmem=0>, the initial amount of memory (memory option in domU
configuration file) assigned to guest will be used as C<minmem>.

=item *

C<minmem_reserve> I<(integer)> -
xenballoond will add C<minmem_reserve> in percent to minimal self
memory target. If guest swaps when balloonind down or if you are
running cache intensive apps, you should increase this value.

=item *

C<preserve_cache> I<(boolean)> -
If enabled, xenballoon will add active cache to the minimum target
memory.

=item *

C<maxmem_file> I<(string)> -
Location where memory high-water mark is stored; if a guest supports
hot-add memory, C<maxmem> might increase across time and the minimum
target heuristic is based on max memory. Note: reboot after changing
this variable, else overballooning may occur.

=item *

C<send_meminfo> I<(boolean)> -
If xenbus is enabled, whether selfballooning or directed ballooning,
place the content of F</proc/meminfo> on xenbus at C<{memory/meminfo}>.

=item *

C<send_vmstat> I<(boolean)> -
If xenbus is enabled, whether selfballooning or directed ballooning,
place the content of F</proc/vmstat> on xenbus at C<{memory/vmstat}>.

=item *

C<send_uptime> I<(boolean)> -
If xenbus is enabled, whether selfballooning or directed ballooning,
place the content of F</proc/uptime> on xenbus at C<{memory/uptime}>.

=item *

C<send_preswap> I<(boolean)> -
If xenbus is enabled, whether selfballooning or directed ballooning,
place the size of preswap (in pages) on xenbus at C<{memory/preswap}>.

=item *

C<send_cpustat> I<(boolean)> -
If xenbus is enabled, place the content of F</proc/loadavg> and
F</proc/stats> on xenbus at C<{cpu_stats}>.

=back


=head1 COPYRIGHT

Copyright 2010-2011 """ + meta.authors + """

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.
"""

# convert the Pod to nroff
pod2man = subprocess.Popen([
    "/usr/bin/pod2man",
    "--name", meta.name,
    "--section", meta.mansect,
    "--center", meta.manbook,
    "--release", meta.name+" v"+meta.version,
    "--stderr",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
)
(output, errors) = pod2man.communicate(input)

if errors:
    sys.stderr.write("errors while generating man page: "+errors)

path = meta.name+"."+meta.mansect
if os.path.isdir("doc"): path = "doc/"+path
open(path, "w").write(output)

