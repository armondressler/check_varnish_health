#!/usr/bin/env python3

#https://blog.pandorafms.org/how-to-monitor-varnish-cache/
#https://www.datadoghq.com/blog/top-varnish-performance-metrics/
#clientside: sess_conn (cummulative), client_req (cmlt), sess_dropped (cmlt)
#cache perf:
#    alle cmlt: cache_hit, cache_miss, cache_hitpass --> cache hit rate = cache_hit / (cache_hit + cache_miss)
#    n_expired (object expired due to ttl), n_lru_nuked (nuked because cache is full)
#thread perf:
#    threads (current), threads_created (cmlt), threads_failed (cmlt, usuccessful creation),
#    threads_limited (cmlt, failed creation due to set limit), thread_queue_len (curr, number of reqs waiting)
#    sess_queued (cmlt, num requests queued up)
#backend per:
#    backend_conn (cmlt, successful tcp conn) backend_recycle (cmltl, kept alive connections back in pool)
#    backend_reuse (cmlt, reused from recycle) backend_toolate (cmlt, closed backend conn for idling)
#    backend_fail (cmlt, failed handshakes with backend) backend_unhealthy (cmlt, not attempted handshakes because
#      wasn't marked healthy) backend_busy (cmlt, occurrence max connections reached) backend_req (req to backend)
#    MAIN.fetch_failed (Fetch failed (all causes), not 1XX, 2XX, 3XX)


import argparse
import operator
import nagiosplugin as nag


__author__ = "Armon Dressler"
__license__ = "Apache"
__version__ = "0.4"
__email__ = "armon.dressler@gmail.com"

'''
Check plugin for monitoring a Varnish instance.
Output is in line with nagios plugins development guidelines.
Copyright 2018 armon.dressler@gmail.com
Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation and/or 
other materials provided with the distribution.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE 
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

class CheckVarnishHealth(nag.Resource):
    
    def __init__(self,
                 metric,
                 backend=None,
                 varnishlog_utility_path=None,
                 nozerocounters=False,
                 min=None,
                 max=None,
                 scan=False):
        pass
        


class CheckVarnishHealthContext(nag.ScalarContext):
    fmt_helper = {
        "active_servers": "{value}{uom} of all servers available are active",
        "http_4XX_pct": "{value}{uom} of all requests returned HTTP 4XX",
        "http_5XX_pct": "{value}{uom} of all requests returned HTTP 5XX or undef",
        "session_capacity_pct": "Operating at {value}{uom} of maximum session capacity",
        "session_rate_capacity_pct": "Session rate reached {value}{uom}",
        ""
        "average_response_time": "Average response time at {value}{uom}",
        "total_megabytes_in": "{value}{uom} received in total",
        "total_megabytes_out": "{value}{uom} sent in total",
        "error_requests": "Got {value} bad requests (disconnect,timeout,ACL hit etc.) from clients",
        "denied_requests": "Discarded {value} requests due to ACL hits (subset of error_requests)",
        "backend_failures": "Counted {value} errors for this resource",
        "queue_capacity_pct": "Queue is at {value}{uom} of maximum capacity",
        "queue_time": "Average time spent in queue is {value}{uom} for the last 1024 requests",
        "new_sessions": "Counted {value} new sessions during previous second",
        "new_requests": "Counted {value} requests during previous second"
    }

    def __init__(self, name, warning=None, critical=None,
                 fmt_metric='{name} is {valueunit}', result_cls=nag.Result):

        try:
            metric_helper_text = CheckVarnishHealthContext.fmt_helper[name]
        except KeyError:
            raise ValueError("Metric \"{}\" not found. Use --help to check for metrics available.".format(name))
        super(CheckVarnishHealthContext, self).__init__(name,
                                                        warning=warning,
                                                        critical=critical,
                                                        fmt_metric=metric_helper_text,
                                                        result_cls=result_cls)


class CheckVarnishHealthSummary(nag.Summary):

    def __init__(self, backend=None):
        if backend:
            self.varnish_resource = backend
            self.mode = "backend"

    def ok(self, results):
        if len(results.most_significant) > 1:
            info_message = ", ".join([str(result) for result in results.results])
        else:
            info_message = " ".join([str(result) for result in results.results])
        return "{} \"{}\" reports: {}".format(self.mode.capitalize(), self.varnish_resource, info_message)

    def problem(self, results):
        if len(results.most_significant) > 1:
            info_message = " ,".join([str(result) for result in results.results])
        else:
            info_message = " ".join([str(result) for result in results.results])
        return "{} \"{}\" reports: {}".format(self.mode.capitalize(), self.varnish_resource, info_message)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-w', '--warning', metavar='RANGE', default='',
                        help='return warning if load is outside RANGE,\
                            RANGE is defined as an number or an interval, e.g. 5:25 or :30  or 95:')
    parser.add_argument('-c', '--critical', metavar='RANGE', default='',
                        help='return critical if load is outside RANGE,\
                            RANGE is defined as an number or an interval, e.g. 5:25 or :30  or 95:')
    parser.add_argument('-u', '--varnishlog-utility-path', action='store', default='/usr/bin/varnishlog',
                        help='path to varnishlog utility')
    varnish_resource_type = parser.add_mutually_exclusive_group(required=True)
    varnish_resource_type.add_argument('--backend', action='store', default=None,
                                  help='name of backend, use --scan to check for resources available')
    varnish_resource_type.add_argument('--scan', action='store_true', default=False,
                                  help='Show Varnish resources available (frontend,backend and server)')
    parser.add_argument('--max', action='store', default=None,
                        help='maximum value for performance data')
    parser.add_argument('--min', action='store', default=None,
                        help='minimum value for performance data')
    parser.add_argument('--metric', action='store', required=False,
                        help='Supported keywords: {}'.format(
                          ", ".join(CheckVarnishHealthContext.fmt_helper.keys())))
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='increase output verbosity (use up to 3 times)')
    parser.add_argument('--nozerocounters', action='store_true', default=False,
                        help='do not zero out stat counters after every run')

    return parser.parse_args()


@nag.guarded
def main():
    args = parse_arguments()
    check = nag.Check(
        CheckVarnishHealth(
            args.metric,
            backend=args.backend,
            varnishlog_utility_path=args.varnishlog_utility_path,
            min=args.min,
            max=args.max,
            scan=args.scan,
            nozerocounters=args.nozerocounters),
        CheckVarnishHealthContext(args.metric, warning=args.warning, critical=args.critical),
        CheckVarnishHealthSummary(backend=args.backend)
    )
    check.main(verbose=args.verbose)


if __name__ == '__main__':
    main()
