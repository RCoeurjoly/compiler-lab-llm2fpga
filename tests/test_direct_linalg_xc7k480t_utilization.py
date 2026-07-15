import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "task3-main" / "scripts" / "pipeline" / "write_nextpnr_xilinx_report.py"
RTLIL_FILTER = (
    ROOT / "task3-main" / "scripts" / "pipeline" / "filter_rtlil_modules.py"
)
UTILIZATION_REPORT = (
    ROOT / "task3-main" / "scripts" / "pipeline" / "write_utilization_report.py"
)


class DirectLinalgXc7k480tUtilizationTest(unittest.TestCase):
    def test_route_status_requires_successful_exit_and_nonempty_fasm(self) -> None:
        cases = [
            (
                None,
                "missing",
                "incomplete",
                "nextpnr exited with status 0 but did not produce a nonempty FASM",
                0,
            ),
            (
                "",
                "empty",
                "incomplete",
                "nextpnr exited with status 0 but did not produce a nonempty FASM",
                0,
            ),
            (
                "# FASM\n",
                "present",
                "success",
                "nextpnr exited with status 0 and produced a nonempty FASM",
                0,
            ),
            (
                "# FASM\n",
                "present",
                "failed",
                "nextpnr exited with status 1",
                1,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            log = work / "nextpnr.log"
            stdout = work / "stdout.log"
            stderr = work / "stderr.log"
            log.write_text("Info: Device utilisation:\n", encoding="utf-8")
            stdout.write_text("route stdout\n", encoding="utf-8")
            stderr.write_text("", encoding="utf-8")

            for (
                contents,
                expected_fasm_status,
                expected_route_status,
                expected_reason,
                exit_status,
            ) in cases:
                with self.subTest(fasm=expected_fasm_status):
                    fasm = work / "design.fasm"
                    report = work / "route.json"
                    if contents is None:
                        fasm.unlink(missing_ok=True)
                    else:
                        fasm.write_text(contents, encoding="utf-8")

                    subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "--nextpnr-log",
                            str(log),
                            "--stdout-log",
                            str(stdout),
                            "--stderr-log",
                            str(stderr),
                            "--exit-status",
                            str(exit_status),
                            "--fasm",
                            str(fasm),
                            "--out",
                            str(report),
                        ],
                        check=True,
                    )
                    payload = json.loads(report.read_text(encoding="utf-8"))

                    self.assertEqual(payload["route"]["exit_status"], exit_status)
                    self.assertEqual(payload["route"]["status"], expected_route_status)
                    self.assertEqual(payload["fasm"]["status"], expected_fasm_status)
                    self.assertEqual(payload["route"]["reason"], expected_reason)

    def test_parser_records_route_frontier_and_arbitrary_device_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            log = work / "nextpnr.log"
            stdout = work / "stdout.log"
            stderr = work / "stderr.log"
            fasm = work / "design.fasm"
            report = work / "route.json"
            log.write_text(
                "\n".join(
                    [
                        "Info: Device utilisation:",
                        "Info:             SLICE_LUT: 123/298600 0%",
                        "Info: custom-routing-widget: 4 / 7 57%",
                        "Info:           MYSTERY-THING: 0/2 0%",
                        "Info: Placing design.",
                        "Info: must-not-be-parsed: 9 / 10 90%",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            stdout.write_text("route stdout\n", encoding="utf-8")
            stderr.write_text("route failed\n", encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--nextpnr-log",
                    str(log),
                    "--stdout-log",
                    str(stdout),
                    "--stderr-log",
                    str(stderr),
                    "--exit-status",
                    "1",
                    "--fasm",
                    str(fasm),
                    "--out",
                    str(report),
                ],
                check=True,
            )
            payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["report_kind"], "nextpnr-xilinx-pnr-report")
        self.assertEqual(payload["route"]["exit_status"], 1)
        self.assertEqual(payload["route"]["status"], "failed")
        self.assertEqual(
            payload["device_utilisation"],
            [
                {"name": "SLICE_LUT", "used": 123, "available": 298600, "pct": 0},
                {
                    "name": "custom-routing-widget",
                    "used": 4,
                    "available": 7,
                    "pct": 57,
                },
                {"name": "MYSTERY-THING", "used": 0, "available": 2, "pct": 0},
            ],
        )
        self.assertEqual(payload["route"]["reason"], "nextpnr exited with status 1")
        self.assertEqual(payload["fasm"]["status"], "missing")

    def test_utilization_counts_boxed_xilinx_modules_as_leaf_primitives(self) -> None:
        design = {
            "modules": {
                "main": {
                    "cells": {
                        "lut": {"type": "LUT6"},
                        "register": {"type": "FDRE"},
                        "wrapper": {"type": "wrapper"},
                    }
                },
                "LUT6": {
                    "attributes": {"blackbox": "1"},
                    "cells": {"simulation_body": {"type": "$not"}},
                },
                "FDRE": {
                    "attributes": {"whitebox": "1"},
                    "cells": {"simulation_body": {"type": "$dff"}},
                },
                "wrapper": {"cells": {"small_lut": {"type": "LUT2"}}},
                "LUT2": {
                    "attributes": {"blackbox": "1"},
                    "cells": {"simulation_body": {"type": "$not"}},
                },
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            design_json = work / "design.json"
            summary_json = work / "summary.json"
            summary_txt = work / "summary.txt"
            stat_json = work / "stat.json"
            design_json.write_text(json.dumps(design), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(UTILIZATION_REPORT),
                    "--design-json",
                    str(design_json),
                    "--top",
                    "main",
                    "--summary-json",
                    str(summary_json),
                    "--summary-txt",
                    str(summary_txt),
                    "--stat-json",
                    str(stat_json),
                    "--capacity-slices",
                    "100",
                    "--capacity-clb-luts",
                    "100",
                    "--capacity-clb-ffs",
                    "100",
                    "--capacity-dsp",
                    "10",
                    "--capacity-bram36",
                    "10",
                    "--capacity-bram-kb",
                    "360",
                ],
                check=True,
            )
            summary = json.loads(summary_json.read_text(encoding="utf-8"))
            stats = json.loads(stat_json.read_text(encoding="utf-8"))

        self.assertEqual(summary["resources"]["clb_luts"]["used"], 2)
        self.assertEqual(summary["resources"]["clb_ffs"]["used"], 1)
        self.assertEqual(
            stats["top_leaf_cell_counts"],
            {"FDRE": 1, "LUT2": 1, "LUT6": 1},
        )

    def test_nested_flake_exports_report_helper_with_pinned_pnr_inputs(self) -> None:
        flake = (ROOT / "task3-main" / "flake.nix").read_text(encoding="utf-8")

        lib_exports = re.search(
            r"\blib\s*=\s*\{\s*inherit\s+(?P<names>[^;]+);",
            flake,
            re.DOTALL,
        )
        self.assertIsNotNone(lib_exports)
        self.assertIn(
            "mkTask3XilinxPnrReport", lib_exports.group("names").split()
        )
        for option in ["--chipdb", "--xdc", "--json", "--fasm", "--log"]:
            self.assertIn(option, flake)
        self.assertIn("write_nextpnr_xilinx_report.py", flake)
        self.assertIn("set +e", flake)
        self.assertRegex(
            flake,
            r'nextpnr-xilinx[\s\S]*?>"\$out/stdout\.log" '
            r'2>"\$out/stderr\.log"\s*'
            r'route_exit_status=\$\?',
        )
        for artifact in [
            '"$out/nextpnr.log"',
            '"$out/stdout.log"',
            '"$out/stderr.log"',
            '"$out/design.fasm"',
            '"$out/route.json"',
        ]:
            self.assertIn(artifact, flake)
        self.assertRegex(
            flake,
            r'write_nextpnr_xilinx_report\.py[\s\S]*?'
            r'--exit-status "\$route_exit_status"[\s\S]*?'
            r'--out "\$out/route\.json"',
        )

    def test_staged_json_preserves_xilinx_primitive_port_directions(self) -> None:
        flake = (ROOT / "task3-main" / "flake.nix").read_text(encoding="utf-8")
        helper = re.search(
            r'mkSynthStageJson\s*=\s*(?P<body>[\s\S]*?)\n\n'
            r'        mkSynthJsonStages\s*=',
            flake,
        )

        self.assertIsNotNone(helper)
        body = helper.group("body")
        self.assertRegex(
            body,
            r'\{\s*name,\s*stageId,\s*stageLabel,\s*inputIl,\s*topName',
        )
        self.assertIn("filter_rtlil_modules.py", body)
        self.assertIn("--keep-reachable-from ${topName}", body)
        self.assertNotIn("drop-escaped-uppercase-modules", body)
        self.assertRegex(
            body,
            r'read_rtlil stage8-reachable\.il\s+'
            r'hierarchy -top \$\{topName\} -check\s+'
            r'proc =\*\s+'
            r'write_json \$out',
        )
        self.assertRegex(
            flake,
            r'stage9\s*=\s*mkSynthStageJson\s*\{[\s\S]*?'
            r'inherit name topName quiet memoryLimitKb;[\s\S]*?'
            r'inputIl\s*=\s*stage8;',
        )

    def test_reachable_rtlil_filter_keeps_only_transitive_module_closure(self) -> None:
        source = """\\
autoidx 17
attribute \\top 1
module \\main
  wire input 1 \\clk
  cell \\FDCE \\state
    connect \\C \\clk
  end
  cell \\wrapper \\wrapped
  end
end
# preserved inter-module comment
attribute \\primitive_kind \"flipflop\"
module \\FDCE
  wire input 1 \\C
end
attribute \\wrapper_attribute 1
module \\wrapper
  cell \\leaf \\child
  end
end
attribute \\leaf_attribute 1
module \\leaf
  wire input 1 \\I
end
module \\unused
  process $proc$unused
    switch \\never
      case 1'0
        assign \\never 1'0
    end
  end
end
# preserved trailing comment

"""
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            input_il = work / "input.il"
            output_il = work / "reachable.il"
            input_il.write_text(source, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(RTLIL_FILTER),
                    "--input",
                    str(input_il),
                    "--output",
                    str(output_il),
                    "--keep-reachable-from",
                    "main",
                ],
                check=True,
            )

            filtered = output_il.read_text(encoding="utf-8")

        self.assertIn("autoidx 17\n", filtered)
        for text in [
            "attribute \\top 1\nmodule \\main\n",
            'attribute \\primitive_kind "flipflop"\nmodule \\FDCE\n',
            "attribute \\wrapper_attribute 1\nmodule \\wrapper\n",
            "attribute \\leaf_attribute 1\nmodule \\leaf\n",
        ]:
            self.assertIn(text, filtered)
        self.assertNotIn("module \\unused", filtered)
        self.assertNotIn("process $proc$unused", filtered)
        self.assertIn("# preserved inter-module comment\n", filtered)
        self.assertIn("# preserved trailing comment\n\n", filtered)
        self.assertLess(filtered.index("module \\main"), filtered.index("module \\FDCE"))
        self.assertLess(
            filtered.index("module \\main"),
            filtered.index("# preserved inter-module comment"),
        )
        self.assertLess(
            filtered.index("# preserved inter-module comment"),
            filtered.index("module \\FDCE"),
        )
        self.assertLess(filtered.index("module \\FDCE"), filtered.index("module \\wrapper"))
        self.assertLess(filtered.index("module \\wrapper"), filtered.index("module \\leaf"))

    def test_legacy_filter_drops_only_escaped_uppercase_modules(self) -> None:
        source = """\\
autoidx 3
# before modules
module \\keep
  wire input 1 \\I
end
# between modules
module \\DropMe
  process $proc$drop
    switch \\I
      case 1'1
        assign \\O 1'0
      end
    end
end
# after modules

"""
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            input_il = work / "input.il"
            output_il = work / "filtered.il"
            input_il.write_text(source, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(RTLIL_FILTER),
                    "--input",
                    str(input_il),
                    "--output",
                    str(output_il),
                    "--drop-escaped-uppercase-modules",
                ],
                check=True,
            )

            filtered = output_il.read_text(encoding="utf-8")

        self.assertIn("autoidx 3\n# before modules\n", filtered)
        self.assertIn("module \\keep\n", filtered)
        self.assertNotIn("module \\DropMe", filtered)
        self.assertNotIn("process $proc$drop", filtered)
        self.assertIn("# between modules\n# after modules\n\n", filtered)

    def test_root_flake_wires_direct_linalg_xc7k480t_mapper_and_pnr(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        route_name = (
            "tinystories-representative-core-w4a8-integer-via-linalg-"
            "no-handshake-xc7k480t"
        )
        source_alias = (
            "tinystories-representative-core-w4a8-integer-via-linalg-"
            "no-handshake-il"
        )

        self.assertRegex(
            flake,
            rf'directLinalgXc7k480tSynthesis\s*=\s*'
            r'task3MainLib\.mkTask3XilinxUtilization\s*\{[\s\S]*?'
            rf'modelIl\s*=\s*pipelineAliasPackages\."{source_alias}";[\s\S]*?'
            r'topName\s*=\s*"main";[\s\S]*?'
            r'capacities\s*=\s*task3TinyStoriesCapacities;',
        )
        self.assertRegex(
            flake,
            rf'directLinalgXc7k480tRouteName\s*=\s*"{route_name}";',
        )
        self.assertRegex(
            flake,
            r'directLinalgXc7k480tProbeXdc\s*=\s*pkgs\.writeText[\s\S]*?'
            r'P&R-only / not a board-function or equivalence interface[\s\S]*?'
            r'set_property PACKAGE_PIN AA28 \[get_ports \{clk\}\][\s\S]*?'
            r'set_property PACKAGE_PIN R28 \[get_ports \{reset\}\][\s\S]*?'
            r'set_property PACKAGE_PIN P30 \[get_ports \{go\}\][\s\S]*?'
            r'set_property PACKAGE_PIN M30 \[get_ports \{done\}\][\s\S]*?'
            r'set_property IOSTANDARD LVCMOS18 \[get_ports \{clk\}\][\s\S]*?'
            r'set_property IOSTANDARD LVCMOS18 \[get_ports \{reset\}\][\s\S]*?'
            r'set_property IOSTANDARD LVCMOS18 \[get_ports \{go\}\][\s\S]*?'
            r'set_property IOSTANDARD LVCMOS18 \[get_ports \{done\}\]',
        )
        self.assertRegex(
            flake,
            r'directLinalgXc7k480tPnrReport\s*=\s*'
            r'task3MainLib\.mkTask3XilinxPnrReport\s*\{[\s\S]*?'
            r'xdc\s*=\s*directLinalgXc7k480tProbeXdc;[\s\S]*?'
            r'designJson\s*=\s*directLinalgXc7k480tSynthesis\.json;',
        )
        direct_mapper = re.search(
            r'directLinalgXc7k480tSynthesis\s*=\s*(?P<body>[\s\S]*?)'
            r'directLinalgXc7k480tProbeXdc\s*=',
            flake,
        )
        self.assertIsNotNone(direct_mapper)
        self.assertNotIn("topSv", direct_mapper.group("body"))
        self.assertRegex(
            flake,
            r'directLinalgXc7k480tManifest\s*=\s*pkgs\.writeText[\s\S]*?'
            r'schema_version\s*=\s*1;[\s\S]*?'
            r'target\s*=\s*\{[\s\S]*?family\s*=\s*"kintex7";[\s\S]*?'
            r'part\s*=\s*"xc7k480tffg1156-1";[\s\S]*?'
            r'chipdb\s*=\s*"xc7k480tffg1156\.bin";[\s\S]*?'
            r'provenance\s*=\s*\{[\s\S]*?'
            r'source_il\s*=\s*"' + re.escape(source_alias) + r'";[\s\S]*?'
            r'top\s*=\s*"main";[\s\S]*?'
            r'nextpnr\s*=\s*\{[\s\S]*?'
            r'url\s*=\s*nextpnrXilinxForkLock\.url;[\s\S]*?'
            r'ref\s*=\s*nextpnrXilinxForkLock\.ref;[\s\S]*?'
            r'revision\s*=\s*nextpnrXilinxForkLock\.rev;',
        )
        for package in [
            f"{route_name}-mapped-utilization",
            f"{route_name}-mapped-json",
            f"{route_name}-probe-xdc",
            f"{route_name}-nextpnr-utilization",
        ]:
            self.assertIn(f'"{package}"', flake)
        self.assertRegex(
            flake,
            r'directLinalgXc7k480tPnrUtilization\s*=\s*pkgs\.runCommand[\s\S]*?'
            r'cp -r \$\{directLinalgXc7k480tPnrReport\}/\. "\$out"[\s\S]*?'
            r'cp \$\{directLinalgXc7k480tSynthesis\.utilization\}/summary\.json\s*\\?\s*'
            r'"\$out/summary\.json"[\s\S]*?'
            r'cp \$\{directLinalgXc7k480tSynthesis\.utilization\}/summary\.txt\s*\\?\s*'
            r'"\$out/summary\.txt"[\s\S]*?'
            r'cp \$\{directLinalgXc7k480tSynthesis\.utilization\}/stat\.json\s*\\?\s*'
            r'"\$out/stat\.json"[\s\S]*?'
            r'cp \$\{directLinalgXc7k480tProbeXdc\} "\$out/probe\.xdc"[\s\S]*?'
            r'cp \$\{directLinalgXc7k480tManifest\} "\$out/manifest\.json"[\s\S]*?'
            r'cp \$\{task3MainLib\.task3Toolchain\.manifest\}\s*\\?\s*'
            r'"\$out/task3-yosys-toolchain\.json"',
        )
        self.assertNotIn(
            'cp -a ${directLinalgXc7k480tPnrReport}/. "$out"', flake
        )


if __name__ == "__main__":
    unittest.main()
