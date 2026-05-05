from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

try:
    import tvm
    from tvm.s_tir import Schedule
    from tvm.s_tir import meta_schedule as ms
    from tvm.script import tir as T
    TVM_IMPORT_ERROR = None
except Exception as err:  # pragma: no cover - environment-dependent
    tvm = None
    Schedule = None
    ms = None
    T = None
    TVM_IMPORT_ERROR = err


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "probe_legacy_baseline_db_bridge.py"
)

spec = importlib.util.spec_from_file_location("probe_legacy_baseline_db_bridge", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


if TVM_IMPORT_ERROR is None:
    @tvm.script.ir_module
    class SimpleElementwise:
        @T.prim_func
        def main(a: T.handle, b: T.handle) -> None:
            T.func_attr({"global_symbol": "main", "tir.noalias": True})
            A = T.match_buffer(a, (4,), "float32")
            B = T.match_buffer(b, (4,), "float32")
            for i in range(4):
                with T.sblock("B"):
                    vi = T.axis.spatial(4, i)
                    B[vi] = A[vi] + T.float32(1)
else:
    SimpleElementwise = None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def reverse_type_name(type_name: str) -> str:
    reverse = {
        "None": "",
        "ffi.String": "runtime.String",
        "ffi.Array": "Array",
        "ffi.Map": "Map",
        "ir.GlobalVar": "GlobalVar",
        "ir.IRModule": "IRModule",
        "ir.IntImm": "IntImm",
        "ir.FloatImm": "FloatImm",
        "ir.PrimType": "PrimType",
        "ir.PointerType": "PointerType",
        "ir.TupleType": "TupleType",
        "ir.FuncType": "FuncType",
        "ir.DictAttrs": "DictAttrs",
        "ir.Range": "Range",
        "ir.SourceMap": "SourceMap",
        "ir.SourceName": "SourceName",
        "tir.SBlock": "tir.Block",
        "tir.SBlockRealize": "tir.BlockRealize",
    }
    return reverse.get(type_name, type_name)


def legacyize_attr_value(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    return value


def legacyize_current_safe_workload_row(workload_row: object) -> object:
    if not isinstance(workload_row, list) or len(workload_row) != 2:
        raise AssertionError(f"unexpected workload row: {workload_row!r}")
    graph = module.decode_streamed_json_payload(workload_row[1])
    legacy_graph: dict[str, object] = {
        "root": graph["root_index"],
        "nodes": [],
        "attrs": graph.get("metadata", {}),
        "b64ndarrays": [],
    }
    for node in graph["nodes"]:
        type_name = node["type"]
        old_type = reverse_type_name(type_name)
        if type_name == "ffi.String":
            legacy_graph["nodes"].append(
                {
                    "type_key": old_type,
                    "repr_str": node["data"],
                }
            )
            continue
        if "data" not in node:
            legacy_graph["nodes"].append({"type_key": old_type})
            continue
        data = node["data"]
        if isinstance(data, dict):
            attrs = {key: legacyize_attr_value(value) for key, value in data.items()}
            if type_name == "tir.PrimFunc":
                attrs["_checked_type_"] = attrs.pop("struct_info_")
            legacy_graph["nodes"].append({"type_key": old_type, "attrs": attrs})
        else:
            legacy_graph["nodes"].append({"type_key": old_type, "data": data})
    return [workload_row[0], module.encode_streamed_json_payload(legacy_graph)]


def legacyize_current_safe_tuning_record_row(record_row: object) -> object:
    if not isinstance(record_row, list) or len(record_row) != 2:
        raise AssertionError(f"unexpected tuning record row: {record_row!r}")
    record = record_row[1]
    trace = record[0]
    legacy_trace = [
        [
            ["GetBlock" if inst[0] == "GetSBlock" else inst[0], inst[1], inst[2], inst[3]]
            for inst in trace[0]
        ],
        trace[1],
    ]
    return [record_row[0], [legacy_trace, record[1], record[2], record[3]]]


@unittest.skipIf(TVM_IMPORT_ERROR is not None, f"tvm unavailable: {TVM_IMPORT_ERROR}")
class ProbeLegacyBaselineDbBridgeTest(unittest.TestCase):
    def patch_project_root(self, project_root: Path) -> None:
        original_root = module.PROJECT_ROOT
        module.PROJECT_ROOT = project_root
        self.addCleanup(setattr, module, "PROJECT_ROOT", original_root)

    def test_normalize_legacy_workload_graph_rewrites_keys_and_type_names(self) -> None:
        legacy_graph = {
            "root": 1,
            "nodes": [
                {"type_key": ""},
                {
                    "type_key": "IRModule",
                    "attrs": {
                        "functions": "2",
                        "global_var_map_": "3",
                        "source_map": "0",
                        "attrs": "0",
                        "global_infos": "4",
                    },
                },
                {"type_key": "Map", "data": [5, 6]},
                {"type_key": "Map", "keys": ["main"], "data": [5]},
                {"type_key": "Map"},
                {
                    "type_key": "GlobalVar",
                    "attrs": {
                        "_checked_type_": "0",
                        "span": "0",
                        "struct_info_": "0",
                        "name_hint": "7",
                    },
                },
                {
                    "type_key": "tir.PrimFunc",
                    "attrs": {
                        "_checked_type_": "8",
                        "attrs": "0",
                        "body": "0",
                        "buffer_map": "4",
                        "params": "9",
                        "ret_type": "10",
                        "span": "0",
                    },
                },
                {"type_key": "runtime.String", "repr_str": "main"},
                {"type_key": "FuncType", "attrs": {"arg_types": "9", "ret_type": "10", "span": "0"}},
                {"type_key": "Array"},
                {"type_key": "TupleType", "attrs": {"fields": "9", "span": "0"}},
            ],
            "attrs": {"tvm_version": "0.20.dev0"},
        }

        normalized, warnings = module.normalize_legacy_workload_graph(legacy_graph)

        self.assertEqual(normalized["root_index"], 1)
        self.assertEqual(normalized["metadata"]["tvm_version"], "0.20.dev0")
        self.assertEqual(normalized["nodes"][1]["type"], "ir.IRModule")
        self.assertEqual(normalized["nodes"][5]["type"], "ir.GlobalVar")
        self.assertNotIn("_checked_type_", normalized["nodes"][5]["data"])
        self.assertEqual(normalized["nodes"][6]["type"], "tir.PrimFunc")
        self.assertEqual(normalized["nodes"][6]["data"]["struct_info_"], 8)
        self.assertEqual(normalized["nodes"][3]["type"], "ffi.Map")
        key_index = normalized["nodes"][3]["data"][0]
        self.assertIsInstance(key_index, int)
        self.assertEqual(normalized["nodes"][key_index]["type"], "ffi.String")
        self.assertEqual(normalized["nodes"][key_index]["data"], "main")
        self.assertEqual(warnings, [])

    def test_probe_recovers_fake_legacyized_current_safe_db(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            project_root = Path(temp_dir_raw)
            self.patch_project_root(project_root)

            source_db = project_root / "baseline_archive" / "tuning_logs"
            source_db.mkdir(parents=True, exist_ok=True)

            sch = Schedule(SimpleElementwise, debug_mask="all")
            block = sch.get_sblock("B", "main")
            sch.annotate(block, "meta_schedule.parallel", 1)
            workload = ms.database.Workload(SimpleElementwise)
            record = ms.database.TuningRecord(sch.trace, workload, [1.0])

            legacy_workload_row = legacyize_current_safe_workload_row(workload.as_json())
            legacy_record_row = legacyize_current_safe_tuning_record_row([0, record.as_json()])
            write_text(
                source_db / "database_workload.json",
                json.dumps(legacy_workload_row, ensure_ascii=False) + "\n",
            )
            write_text(
                source_db / "database_tuning_record.json",
                json.dumps(legacy_record_row, ensure_ascii=False) + "\n",
            )

            rc = module.main(
                [
                    "--source-db",
                    str(source_db),
                    "--report-id",
                    "unit_legacy_bridge_probe",
                    "--output-dir",
                    str(project_root / "output"),
                ]
            )

            self.assertEqual(rc, 0)
            summary_path = (
                project_root
                / "session_bootstrap"
                / "reports"
                / "unit_legacy_bridge_probe.json"
            )
            self.assertTrue(summary_path.is_file())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(
                summary["workload_graph_formats"],
                {"legacy_root_object_graph": 1},
            )
            self.assertTrue(summary["normalized_probe"]["workloads"]["success"])
            self.assertTrue(summary["normalized_probe"]["tuning_records"]["success"])
            self.assertEqual(summary["trace_ops"]["unsupported_ops"], {"GetBlock": 1})
            self.assertEqual(summary["trace_ops"]["rewrite_counts"], {"GetBlock": 1})
            self.assertTrue(summary["candidate_db"]["parse_validated"])
            candidate_dir = Path(summary["candidate_db"]["candidate_dir"])
            self.assertTrue((candidate_dir / "database_workload.json").is_file())
            self.assertTrue((candidate_dir / "database_tuning_record.json").is_file())


if __name__ == "__main__":
    unittest.main()
