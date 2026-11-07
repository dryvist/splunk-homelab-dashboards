import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "default/data/ui/views"


def dashboard(name):
    definition = ET.parse(VIEWS / f"{name}.xml").getroot().findtext("definition")
    assert definition is not None, f"{name} has no definition"
    return json.loads(definition)


class StudioAgentViewsTest(unittest.TestCase):
    def test_event_searches_share_selected_time_with_valid_chain_parents(self):
        for name in ("agent_timeline", "agent_network"):
            with self.subTest(view=name):
                view = dashboard(name)
                self.assertEqual(view["layout"]["globalInputs"], ["input_time"])
                self.assertEqual(
                    view["inputs"]["input_time"]["options"]["defaultValue"], "-4h,now"
                )
                self.assertEqual(
                    view["defaults"]["dataSources"]["ds.search"]["options"][
                        "queryParameters"
                    ],
                    {"earliest": "$time.earliest$", "latest": "$time.latest$"},
                )
                sources = view["dataSources"]
                self.assertEqual(
                    sum(source["type"] == "ds.search" for source in sources.values()), 1
                )
                for source_id, source in sources.items():
                    query = source["options"]["query"]
                    if source["type"] == "ds.chain":
                        parent = source["options"]["extend"]
                        self.assertIn(parent, sources)
                        self.assertNotEqual(parent, source_id)
                        self.assertEqual(sources[parent]["type"], "ds.search")
                        self.assertTrue(query.startswith("|"))
                    else:
                        self.assertRegex(
                            query, r"^\(?index=hermes sourcetype=hermes:agent"
                        )
                        self.assertIn("| spath", query)
                    for forbidden in (
                        "index=*",
                        "makeresults",
                        "random(",
                        "fillnull",
                        "transaction",
                        "duration_ms",
                        "malloc_trim",
                        "rss_kib",
                        "rss_mb",
                        "in_use",
                        "run_id",
                        "component",
                        "event_type",
                        "operation_name",
                    ):
                        self.assertNotIn(forbidden, query)

    def test_timeline_binds_model_latency_and_bounded_lifecycle_intervals(self):
        view = dashboard("agent_timeline")
        viz = view["visualizations"]["viz_timeline"]
        self.assertEqual(viz["type"], "splunk.timeline")
        options = viz["options"]
        for option, field in (
            ("x", "_time"),
            ("y", "lane"),
            ("duration", "interval_ms"),
            ("category", "category"),
        ):
            self.assertEqual(options[option], f"> primary | seriesByName('{field}')")
        base = view["dataSources"]["ds_events"]["options"]["query"]
        self.assertNotIn("index=hindsight", base)
        self.assertIn("rex field=message", base)
        self.assertIn("rex field=latency", base)
        self.assertIn('tonumber(latency_value)*if(latency_unit="s",1000,1)', base)
        self.assertIn('host_key=coalesce(host,"")', base)
        self.assertIn('procid_key=coalesce(procid,"")', base)
        self.assertIn("| addinfo", base)
        query = view["dataSources"]["ds_intervals"]["options"]["query"]
        self.assertIn("sort 50000 - _time - lifecycle_order - _indextime - _cd", query)
        self.assertIn("streamstats window=10000 global=f current=f", query)
        self.assertIn("BY host_key procid_key unit", query)
        self.assertIn('lifecycle="Starting"', query)
        self.assertIn('isnull(next_state) OR next_state!="Starting"', query)
        self.assertIn("range_end=min(now(),info_max_time)", query)
        self.assertIn('isnull(next_state),"running"', query)
        self.assertIn('match(next_state,"^Failed"),"failed"', query)
        self.assertIn('"model calls"', query)
        self.assertIn('"model: ".model', query)
        self.assertIn("1000*(coalesce(next_time,range_end)-_time)", query)
        self.assertIn("1000*_time-call_ms,1000*_time", query)
        self.assertIn("where isnotnull(interval_ms) AND interval_ms>=0", query)

    def test_lifecycle_and_latency_extractors_accept_real_message_shapes(self):
        base = dashboard("agent_timeline")["dataSources"]["ds_events"]["options"][
            "query"
        ]
        patterns = re.findall(r'rex field=(\w+) "([^"]+)"', base)
        lifecycle, result, latency = [
            re.compile(pattern.replace("(?<", "(?P<")) for _, pattern in patterns
        ]
        for state in ("Starting", "Finished", "Failed to start", "Failed", "Stopped"):
            with self.subTest(state=state):
                match = lifecycle.search(f"{state} agent-job.service - Agent job.")
                assert match is not None
                self.assertEqual(match["unit"], "agent-job.service")
                self.assertEqual(match["lifecycle"], state)
        for state in ("Failed", "Deactivated"):
            match = result.search(f"agent-job.service: {state} with result.")
            assert match is not None
            self.assertEqual(match["result_unit"], "agent-job.service")
            self.assertEqual(match["result_state"], state)
        for value, expected_ms in (("1.6s", 1600), ("25ms", 25), ("0s", 0)):
            match = latency.fullmatch(value)
            assert match is not None
            factor = 1000 if match["latency_unit"] == "s" else 1
            self.assertEqual(float(match["latency_value"]) * factor, expected_ms)
        for value in ("-1s", "25", "nan", "1.6seconds"):
            self.assertIsNone(latency.fullmatch(value))
        self.assertIsNone(lifecycle.search("memory trim completed in 25ms"))

    def test_network_counts_nodes_separately_from_expanded_edges(self):
        view = dashboard("agent_network")
        sources = view["dataSources"]
        base = sources["ds_relationships"]["options"]["query"]
        # SPL binds OR tighter than the implicit AND, so each index needs its own group.
        self.assertTrue(base.startswith(
            "(index=hermes sourcetype=hermes:agent) OR (index=hindsight sourcetype=hindsight:app) |"
        ))
        self.assertIn("stats count AS events sum(deny_event) AS denies BY", base)
        for field in (
            "plugin",
            "decision",
            "model",
            "latency",
            "provider",
            "bank",
            "store",
        ):
            self.assertRegex(base, rf"\b{field}\b")
        self.assertIn('relation="plugin" AND decision="deny",1,0', base)
        self.assertIn('"bank: hindsight / ".bank', base)
        self.assertIn('if(match(store,"^[0-9]"),"hindsight",store)', base)
        self.assertNotIn("api_base", base)
        edges = sources["ds_edges"]["options"]["query"]
        # mvappend of numeric literals yields no hop values; split builds the two hops.
        self.assertIn('hop=split("0,1",",") | mvexpand hop', edges)
        self.assertIn('target=if(hop="0",middle,destination)', edges)
        self.assertIn("where len(target)>0", edges)
        self.assertIn(
            "stats sum(events) AS events sum(denies) AS deny_count BY source target",
            edges,
        )
        self.assertEqual(edges.count("mvexpand"), 1)
        nodes = sources["ds_nodes"]["options"]["query"]
        self.assertIn("mvdedup(mvappend(origin,middle,", nodes)
        self.assertIn("stats sum(events) AS events BY node", nodes)
        self.assertNotIn("hop", nodes)
        viz = view["visualizations"]["viz_network"]
        self.assertEqual(viz["type"], "splunk.networkGraph")
        self.assertEqual(
            viz["dataSources"], {"primary": "ds_edges", "nodeSource": "ds_nodes"}
        )
        options = viz["options"]
        for option, field in (("source", "source"), ("target", "target")):
            self.assertEqual(options[option], f"> primary | seriesByName('{field}')")
        self.assertEqual(options["nodeIds"], "> nodeSource | seriesByName('node')")
        self.assertEqual(options["nodeValues"], "> nodeSource | seriesByName('events')")
        self.assertEqual(
            options["nodeSize"],
            "> nodeSource | seriesByName('events') | lerp(nodeScale)",
        )
        self.assertEqual(
            options["linkWidth"], "> primary | seriesByName('events') | lerp(edgeScale)"
        )
        self.assertEqual(options["showDirection"], "oneWay")
        self.assertNotIn("linkLabels", options)
        table = view["visualizations"]["viz_edges"]
        self.assertEqual(table["type"], "splunk.table")
        self.assertEqual(table["dataSources"], {"primary": "ds_edges"})

    def test_readme_lists_required_versions(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("| Agent timeline (Beta) | `agent_timeline` | 10.2+ |", readme)
        self.assertIn("| Agent network (Beta) | `agent_network` | 10.4+ |", readme)


if __name__ == "__main__":
    unittest.main()
