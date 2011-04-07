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

...


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

