#!/usr/bin/env python3

# https://blog.pandorafms.org/how-to-monitor-varnish-cache/
# https://www.datadoghq.com/blog/top-varnish-performance-metrics/
# clientside: sess_conn (cummulative), client_req (cmlt), sess_dropped (cmlt)
# cache perf:
#    alle cmlt: cache_hit, cache_miss, cache_hitpass --> cache hit rate = cache_hit / (cache_hit + cache_miss)
#    n_expired (object expired due to ttl), n_lru_nuked (nuked because cache is full)
# thread perf:
#    threads (current), threads_created (cmlt), threads_failed (cmlt, usuccessful creation),
#    threads_limited (cmlt, failed creation due to set limit), thread_queue_len (curr, number of reqs waiting)
#    sess_queued (cmlt, num requests queued up)
# backend per:
#    backend_conn (cmlt, successful tcp conn) backend_recycle (cmltl, kept alive connections back in pool)
#    backend_reuse (cmlt, reused from recycle) backend_toolate (cmlt, closed backend conn for idling)
#    backend_fail (cmlt, failed handshakes with backend) backend_unhealthy (cmlt, not attempted handshakes because
#      wasn't marked healthy) backend_busy (cmlt, occurrence max connections reached) backend_req (req to backend)
#    MAIN.fetch_failed (Fetch failed (all causes), not 1XX, 2XX, 3XX)


import argparse
import operator
import nagiosplugin as nag
from subprocess import Popen, PIPE
from json import loads
try:
    from json import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
from os.path import join,exists,isdir
import logging


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
                 varnishlog_utility_path=None,
                 varnish_instance_name=None,
                 tmpdir=None,
                 min=None,
                 max=None):
        self.metric = metric
        self.varnishlog_utility_path = varnishlog_utility_path
        self.varnish_instance_name = varnish_instance_name
        self.tmpfile = join(tmpdir, metric)
        self.min = min
        self.max = max
        self.logger = logging.getLogger('nagiosplugin')

    def client_good_request_rate(self):
        metric_value_dict = self._fetch_varnishstats(["MAIN.client_req"])
        with nag.Cookie(statefile=self.tmpfile) as cookie:
            historic_value = cookie.get("MAIN.client_req")
            if historic_value is not None:
                metric_value = int(metric_value_dict["MAIN.client_req"]) - historic_value
                cookie["MAIN.client_req"] = metric_value_dict["MAIN.client_req"]
                cookie.commit()
            else:
                metric_value = 0
                cookie["MAIN.client_req"] = metric_value_dict["MAIN.client_req"]
                cookie.commit()
        return {
            "value": metric_value,
            "name": "client_good_request_rate",
            "uom": "%",
            "min": 0}

    def _get_percentage(self, part, total):
        try:
            part = sum(part)
        except TypeError:
            pass
        try:
            total = sum(total)
        except TypeError:
            pass
        try:
            ret_val = round(part / total * 100, 2)
        except ZeroDivisionError:
            ret_val = 0
        return ret_val

    def _load_varnishstats_json(self, varnish_output, fieldlist):
        """
        returns dict with varnish fields (e.g. MGT.child_died) and their corresponding values
        :param varnish_output: string, must be valid json
        :param fieldlist: list of strings of varnish stat fields
        :return: dict()
        """
        try:
            result_dict = loads(varnish_output)
        except JSONDecodeError:
            self.logger.error("Failed to decode json for fields {} from varnish output: {}".format(
                ", ".join(fieldlist),
                varnish_output))
            raise
        return {field: value["value"] for (field, value) in result_dict.items() if field in fieldlist}

    def _fetch_varnishstats(self, fieldlist):
        """
        Grab raw stats from varnish daemon
        :param fieldlist: list of strings of varnish stat fields
        :return: dict()
        """
        extended_fieldlist = [("-f", field) for field in fieldlist]
        arglist = [self.varnishlog_utility_path, "-j", "-1"] + [arg for pair in extended_fieldlist for arg in pair]
        self.logger.debug("Starting varnishstats ({}) with args {}".format(arglist[0], ", ".join(arglist[1:])))
        process = Popen(arglist, stdout=PIPE)
        stdout, stderr = process.communicate()
        stdout_string = stdout.decode()
        exit_status = process.wait(timeout=3)
        return self._load_varnishstats_json(stdout_string, fieldlist)

    def probe(self):
        metric_dict = operator.methodcaller(self.metric)(self)
        if self.min:
            metric_dict["min"] = self.min
        if self.max:
            metric_dict["max"] = self.max
        return nag.Metric(metric_dict["name"],
                          metric_dict["value"],
                          uom=metric_dict.get("uom"),
                          min=metric_dict.get("min"),
                          max=metric_dict.get("max"),
                          context=metric_dict.get("context"))


class CheckVarnishHealthContext(nag.ScalarContext):
    fmt_helper = {
        "client_good_request_rate": "{values} client requests, not subject to 4XX response",
        "client_bad_request_rate": "{value} client requests subject to 4XX response",
        "cache_hitrate_pct": "{value}{uom} of requests satisfied by cache",
        "cache_hitforpass_rate": "{value} of requests marked hit for pass",
        "cached_objects_expired_rate": "{value} objects expired due to ttl",
        "cached_objects_nuked_rate": "{value} objects nuked from cache due to saturation",
        "threads_failed_rate": "failed to create {value} threads",
        "threads_failed_at_limit_rate": "failed to create {value} threads because of configured limit",
        "session_queue_rate": "{value} sessions waiting for a worker thread",
        "backend_request_rate": "{value} backend requests sent",
        "backend_connection_rate": "{value} backend connections",
        "backend_connection_saturation_rate": "max backend connections reached for {value} time(s)",
        "backend_unattempted_connections_rate": "{value} connections to backend not attempted due to unhealthy status",

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
    parser.add_argument('-u', '--varnishlog-utility-path', action='store', default='/usr/bin/varnishstat',
                        help='path to varnishlog utility')
    parser.add_argument('-n', '--varnish-instance-name', action='store', help='hostname by default')
    parser.add_argument('-t', '--tmpdir', action='store', default='/tmp/check_varnish_health',
                        help='path to directory to store delta files')
    parser.add_argument('--max', action='store', default=None,
                        help='maximum value for performance data')
    parser.add_argument('--min', action='store', default=None,
                        help='minimum value for performance data')
    parser.add_argument('--metric', action='store', required=True,
                        help='Supported keywords: {}'.format(
                            ", ".join(CheckVarnishHealthContext.fmt_helper.keys())))
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='increase output verbosity (use up to 3 times)')

    return parser.parse_args()


@nag.guarded
def main():
    args = parse_arguments()
    check = nag.Check(
        CheckVarnishHealth(
            args.metric,
            varnishlog_utility_path=args.varnishlog_utility_path,
            varnish_instance_name=args.varnish_instance_name,
            tmpdir=args.tmpdir,
            min=args.min,
            max=args.max),
        CheckVarnishHealthContext(args.metric, warning=args.warning, critical=args.critical),
        CheckVarnishHealthSummary()
    )
    check.main(verbose=args.verbose)


if __name__ == '__main__':
    main()
