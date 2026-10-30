import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "default/data/ui/views"


class DashboardViewsTest(unittest.TestCase):
    def test_every_view_is_dashboard_studio_xml_with_valid_json(self):
        view_files = sorted(VIEWS.glob("*.xml"))
        self.assertEqual(
            {path.stem for path in view_files},
            {"homelab_overview", "storage_capacity_health"},
        )

        for path in view_files:
            with self.subTest(view=path.name):
                root = ET.parse(path).getroot()
                self.assertEqual(root.tag, "dashboard")
                self.assertEqual(root.get("version"), "2")
                definition = root.findtext("definition")
                self.assertIsNotNone(definition)
                dashboard = json.loads(definition)
                data_sources = dashboard["dataSources"]
                visualizations = dashboard["visualizations"]
                for visualization in visualizations.values():
                    for source_id in visualization.get("dataSources", {}).values():
                        self.assertIn(source_id, data_sources)
                for input_definition in dashboard.get("inputs", {}).values():
                    items = input_definition.get("options", {}).get("items", {})
                    for source_id in items.get("dataSources", {}).values():
                        self.assertIn(source_id, data_sources)
                for block in dashboard["layout"]["structure"]:
                    self.assertIn(block["item"], visualizations)

    def test_navigation_lists_both_dashboards(self):
        nav = ET.parse(ROOT / "default/data/ui/nav/default.xml").getroot()
        self.assertEqual(
            {view.get("name") for view in nav.findall("view")},
            {"homelab_overview", "storage_capacity_health"},
        )


if __name__ == "__main__":
    unittest.main()
