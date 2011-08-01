#!/usr/bin/env python
""" Command-line frontend """

import atexit, os, signal, sys, syslog
import ConfigParser
from   optparse import OptionParser, SUPPRESS_HELP
import meta, xenballoon


#
# parse_options()
# -------------
## Parse command line options
# @return an OptionParser object
#
def parse_options():
    """ Parse command line options and return an OptionParser object """

    parser = OptionParser()

    parser.add_option("-V", "--version",
        dest="version", action="store_true",
        help="Show the program name and version and exit.")

    parser.add_option("-c", "--config",
        dest="config", type="string", metavar="FILE",
        default="/etc/"+meta.name+".conf",
        help="Specify an alternate path to the configuration file.")

    parser.add_option("-D", "--detach",
        dest="detach", action="store_true", default=True,
        help="Make the program act as a daemon, detaching itself "
             "from the current terminal.")

    parser.add_option("--nodetach","--no-detach",
        dest="detach", action="store_false", help=SUPPRESS_HELP)

    parser.add_option("-p", "--pidfile",
        dest="pidfile", type="string",
        default="/var/run/"+meta.name+".pid",
        help="Specify the path to the PID file.")

    return parser.parse_args()


#
# become_daemon()
# -------------
def become_daemon():
    """
    Properly detach the process from its parent to become a daemon

    This function is an extremely lightweight, self-hosted version
    of PEP 3143 python-daemon library.
    """

    def fork_detach():
        try:
            if os.fork() > 0: os._exit(0)
        except OSError, err:
            sys.stderr.write("fork failed: [%d] %s\n" % (err.errno, err.strerror))

    def redirect_to_devnull(stream):
        devnull_fd = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull_fd, stream.fileno())

    os.umask(0)     # clear file creation mask
    os.chdir("/")   # change working directory to /
    fork_detach()   # first fork
    os.setsid()     # detach and become a new session leader
    fork_detach()   # second fork
    redirect_to_devnull(sys.stdin)  # redirect stdin  to /dev/null
    redirect_to_devnull(sys.stdout) # redirect stdout to /dev/null
    redirect_to_devnull(sys.stderr) # redirect stderr to /dev/null


#
# run()
# ---
def run():
    """ Entry function """

    me = (meta.name, meta.version)

    # parse command line options
    (options, args) = parse_options()

    if options.version:
        print "%s v%s" % me
        return

    # read configuration file
    config = ConfigParser.ConfigParser()
    config.read(options.config)

    # instanciate the backend objet
    backend = xenballoon.Xenballoon(config)

    # early checks and initialisations
    backend.init()

    # become a daemon is asked to do so
    if options.detach:
        become_daemon()

    # store PID
    open(options.pidfile, "w").write(str(os.getpid()))

    # open syslog
    syslog.openlog(meta.name, syslog.LOG_PID|syslog.LOG_NDELAY|syslog.LOG_PERROR,
        syslog.LOG_DAEMON)
    syslog.syslog(syslog.LOG_INFO, "%s v%s starting" % me)

    # register on-exit cleaning handler
    def clean_on_exit():
        os.unlink(options.pidfile)
        syslog.syslog(syslog.LOG_INFO, "%s v%s stopped" % me)

    atexit.register(clean_on_exit)

    # register signal handler
    def sighandler(signum, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, sighandler)

    # enter main loop
    backend.run()

