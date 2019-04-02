## check_varnish_health
#### Nagios compliant monitoring script to report metrics gathered from varnishstat

The installation requires python3 and the module "nagiosplugin" (by Christian Kauhaus).

For an icinga2 sample config, see directory "icinga2_sample_configs".


### Basic Usage:

#### Show options and their respective explanations.

    ./check_javamelody_health.py --help
```
usage: check_varnish_health [-h] [-w RANGE] [-c RANGE]
                            [-u VARNISHSTAT_UTILITY_PATH]
                            [-n VARNISH_INSTANCE_NAME] [-t TMPDIR] [--max MAX]
                            [--min MIN] --metric METRIC [-v]

optional arguments:
  -h, --help            show this help message and exit
  -w RANGE, --warning RANGE
                        return warning if load is outside RANGE, RANGE is
                        defined as an number or an interval, e.g. 5:25 or :30
                        or 95:
  -c RANGE, --critical RANGE
                        return critical if load is outside RANGE, RANGE is
                        defined as an number or an interval, e.g. 5:25 or :30
                        or 95:
  -u VARNISHSTAT_UTILITY_PATH, --varnishstat-utility-path VARNISHSTAT_UTILITY_PATH
                        path to varnishstat utility
  -n VARNISH_INSTANCE_NAME, --varnish-instance-name VARNISH_INSTANCE_NAME
                        hostname by default
  -t TMPDIR, --tmpdir TMPDIR
                        path to directory to store delta files
  --max MAX             maximum value for performance data
  --min MIN             minimum value for performance data
  --metric METRIC       Supported keywords: client_bad_request_rate,
                        client_good_request_rate, cache_hitrate_pct,
                        session_queue_rate, threads_creation_rate,
                        backend_request_rate, cached_objects_expired_rate,
                        cache_hitforpass_rate, threads_failed_rate,
                        cached_objects_nuked_rate,
                        backend_connection_saturation_rate,
                        backend_unattempted_connections_rate,
                        backend_connection_rate, threads_failed_at_limit_rate,
                        backend_failed_request_rate
  -v, --verbose         increase output verbosity (use up to 2 times)

```

The -u option refers to the varnishstat binary (defaults to /usr/bin/varnishstat)
The -n option won't be needed usually, see the -n option in "man varnishstat" for further reading. 
The tmpdir refered to by -t (defaults to /tmp/check_varnish_health) will be created by the plugin, 
make sure the system user running your monitoring daemon has the appropriate permissions to do so.
This includes configuring SELinux where necessary. Permissions will be set to 750.


#### Get current cache hitrate

    ./check_varnish_health.py --metric cache_hitrate_pct
    
```text
CHECKVARNISHHEALTH OK - varnish reports: 98.13% of requests satisfied by cache | cache_hitrate_pct=98.13%;;;0;100
```

#### Get backend connection rate (change since last check execution) and set check to warning if above 200 and critical if above 300, save state under /tmp/icinga2_tmpmetrics 

    ./check_javamelody_health.py -t /tmp/icinga2_tmpmetrics --metric backend_connection_rate -w :200 -c :300

```text
CHECKVARNISHHEALTH OK - varnish reports: 3 backend connection(s) initiated | backend_connection_rate=3c;200;300;0
``` 
