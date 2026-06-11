"""
EAM QEA Analyzer — Open WebUI Tool
===================================
AAroN-informed QEA file analyzer for Sparx Enterprise Architect models.
Extracts and leverages AAroN's deep knowledge of the proprietary QEA table structure.

Based on: https://github.com/schmitze87/AAroN (Apache 2.0)
Knowledge extracted from AAroN's 15+ table processors and EA model classes.

Usage as Open WebUI Tool:
    Drop this file into Open WebUI's tools directory.
    The LLM can then call these functions to analyze QEA files.

Author: Michael Estel — Built from AAroN source analysis
Date: 2026-06-06
requirements: networkx, pandas
"""

import sqlite3
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

import networkx as nx
import pandas as pd


# ═══════════════════════════════════════════════════════════════
# AAroN-DERIVED TABLE SCHEMA KNOWLEDGE
# ═══════════════════════════════════════════════════════════════
# These mappings are extracted from AAroN's Java model classes
# (EAObject.java, EAConnector.java, EAPackage.java, etc.)

# Processing order matters! (from SparxSQLiteConverter.java:38-63)
TABLE_PROCESSING_ORDER = [
    "t_system",           # System info (project GUID, name)
    "t_package",          # Package hierarchy FIRST
    "t_diagram",          # Diagrams
    "t_object",           # Elements/Objects (the core table)
    "t_objectproperties", # Tagged Values on objects
    "t_objectconstraints",
    "t_connector",        # Relationships between objects
    "t_connectortag",     # Tagged Values on connectors
    "t_connectorconstraints",
    "t_diagramobjects",   # Objects on diagrams
    "t_diagramlinks",     # Connector styling on diagrams
    "t_operation",        # Operations/Methods
    "t_operationtag",
    "t_operationparams",
    "t_attribute",        # Attributes
    "t_attributetag",
    "t_attributeconstraints",
    "t_xref",             # Cross-references (stereotypes, conveyed items, etc.)
]

# === Core table schemas (AAroN-derived) ===

# t_object: The main element table (EAObject.java)
# Object_Type values: Class, Component, Node, Package, Requirement,
#   Action, Object, Part, Port, Interface, Activity, State, Event,
#   UseCase, Actor, Artifact, DeploymentSpec, Collaboration, etc.
OBJECT_KEY_COLUMNS = [
    "Object_ID", "Object_Type", "Name", "Alias", "Author",
    "Note", "Stereotype", "Package_ID", "ParentID", "ea_guid",
    "PDATA1", "PDATA2", "PDATA3", "PDATA4", "PDATA5",
    "Classifier", "Classifier_guid", "Status", "Phase",
    "Complexity", "Version", "CreatedDate", "ModifiedDate",
    "Visibility", "Scope", "Abstract", "IsRoot", "IsLeaf",
    "IsActive", "IsSpec", "Multiplicity", "RunState",
    "Cardinality", "Concurrency", "Persistence",
    "GenType", "GenFile", "Header1", "Header2",
    "StyleEx", "StateFlags", "ActionFlags", "EventFlags",
    "PackageFlags", "TPos", "Tagged", "NType",
]

# t_connector: Relationships between objects (EAConnector.java)
CONNECTOR_KEY_COLUMNS = [
    "Connector_ID", "Name", "Connector_Type", "Stereotype",
    "Direction", "Notes",
    "Start_Object_ID", "End_Object_ID",
    "SourceRole", "SourceRoleType", "SourceRoleNote",
    "DestRole", "DestRoleType", "DestRoleNote",
    "SourceCard", "DestCard",
    "SourceAccess", "DestAccess",
    "SourceElement", "DestElement",
    "SourceContainment", "DestContainment",
    "SourceIsAggregate", "DestIsAggregate",
    "SourceIsOrdered", "DestIsOrdered",
    "SourceIsNavigable", "DestIsNavigable",
    "SourceChangeable", "DestChangeable",
    "SourceConstraint", "DestConstraint",
    "SourceQualifier", "DestQualifier",
    "SourceStereotype", "DestStereotype",
    "SourceStyle", "DestStyle",
    "PDATA1", "PDATA2", "PDATA3", "PDATA4", "PDATA5",
    "DiagramID", "ea_guid",
    "IsRoot", "IsLeaf", "IsSpec",
    "IsSignal", "IsStimulus",
    "StateFlags", "ActionFlags", "EventFlags",
    "StyleEx", "VirtualInheritance", "LinkAccess",
    "Top_Start_Label", "Top_Mid_Label", "Top_End_Label",
    "Btm_Start_LAbel", "Btm_Mid_Label", "Btm_End_Label",
    "DispatchAction", "Target2",
]

# AAroN-DISCOVERED IMPLICIT RELATIONSHIPS (ObjectProcessor.java:155-292)
# These are NOT stored as t_connector rows but derived from t_object column logic
IMPLICIT_RELATIONSHIPS = {
    "CONTAINS": {
        "from": "Package", "to": "Object",
        "source": "t_package.Package_ID → t_object.Package_ID",
        "note": "Every object belongs to a package via Package_ID"
    },
    "BEHAVIOUR": {
        "from": "Action", "to": "Behaviour-Element",
        "source": "t_object.PDATA1 → t_object.ea_guid (when Object_Type='Action')",
        "note": "Action elements reference their behavioural element via PDATA1 GUID"
    },
    "CLASSIFIER": {
        "from": "Object/Action", "to": "Classifier",
        "source": "t_object.Classifier_guid → t_object.ea_guid",
        "note": "Objects typed by a classifier (e.g., InstanceOf in UML)"
    },
    "INSTANCE_OF": {
        "from": "Object/Part/Port", "to": "Classifier-Element",
        "source": "t_object.PDATA1 → t_object.ea_guid",
        "note": "Parts/Ports reference their type via PDATA1 GUID"
    },
    "REUSAGE": {
        "from": "Part/Port", "to": "Reused-Element",
        "source": "t_object.PDATA3 → t_object.ea_guid",
        "note": "Parts reference their reused element via PDATA3 GUID"
    },
    "HAS_PORT": {
        "from": "Parent-Element", "to": "Port",
        "source": "t_object.ParentID → t_object.Object_ID (when Object_Type='Port')",
        "note": "Ports belong to a parent element via ParentID"
    },
    "HAS_PART": {
        "from": "Parent-Element", "to": "Part",
        "source": "t_object.ParentID → t_object.Object_ID (when Object_Type='Part')",
        "note": "Parts belong to a parent via ParentID"
    },
    "EMBEDS": {
        "from": "Parent-Element", "to": "Child-Element",
        "source": "t_object.ParentID → t_object.Object_ID (generic embedding)",
        "note": "Generic parent-child embedding for any Object_Type"
    },
    "HAS_PARENT": {
        "from": "Child-Element", "to": "Parent-Element",
        "source": "t_object.ParentID → t_object.Object_ID (inverse of EMBEDS)",
        "note": "Inverse embedding relationship"
    },
}

# NAF view type mapping (derived from NAF architecture knowledge)
NAF_VIEW_STEREOTYPES = {
    "NAF-2": ["Ov-2", "OpNode", "Needline", "InformationExchange"],
    "NAF-3": ["Capability", "CapabilityConfiguration", "CapabilityDependency"],
    "NAF-4": ["Ov-4", "OrganizationalResource", "OrganizationRole"],
    "NAF-5": ["Sv-5", "Function", "Activity", "OperationalActivity"],
    "NAF-6": ["Sv-6", "SystemResource", "ResourceInteraction"],
    "NAF-7": ["Tv-7", "Protocol", "Standard", "TechnicalStandard"],
}

# Tagged Value Tables (NAF-critical!)
# t_objectproperties: property_id, object_id, property, value, notes, ea_guid
# t_connectortag: property_id, element_id, property, value, notes, ea_guid
# t_attributetag: property_id, element_id, property, value, notes, ea_guid


# Diagram-based activity process extraction constants (ported from local pipeline).
DIAGRAM_ALLOWED_CONNECTOR_TYPES = {"ControlFlow", "StateFlow", "Transition"}
ALLOWED_FLOW_NODE_TYPES = {"Action", "Decision", "Event"}

BANNED_OBJECT_TYPES = {"Package", "Text", "Issue"}
BANNED_STEREOTYPES = {
    "Classification",
    "ResourceRole",
    "RequirementCategory",
    "Viewpoint",
    "Concern",
    "OperationalConstraint",
    "InformationElement",
    "DataElement",
    "FunctionalRequirement",
    "OperationalRole",
    "Project",
    "Standard",
    "OperationalPerformer",
    "ActualProject",
    "Recommendation",
    "Finding",
}


MAX_PROCESS_RESPONSE_CHARS = 120000


def _guard_process_response_size(obj: Any, label: str = "process_response") -> Any:
    text = json.dumps(obj, ensure_ascii=False, default=str)
    if len(text) > MAX_PROCESS_RESPONSE_CHARS:
        raise ValueError(
            f"{label} too large: {len(text)} chars. "
            "Use compact listing or tighter max_nodes/max_edges limits."
        )
    return obj


def pg_clean_str(value: Any) -> str:
    if value is None:
        return ""
    s = str(value)
    return "" if s.lower() == "nan" else s


def pg_normalize_whitespace(value: Any) -> str:
    return " ".join(pg_clean_str(value).split())


def pg_safe_snippet(value: Any, max_chars: int = 500) -> str:
    text = pg_clean_str(value)
    return text if len(text) <= max_chars else text[:max_chars] + "..."


def pg_node_evidence_id(activity_id: int, object_id: int) -> str:
    return f"EA:Activity:{activity_id}:Object:{object_id}"


def pg_to_int(value: Any) -> int:
    if value is None:
        return 0
    s = str(value).replace("nan", "").strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def pg_pick_col(row: dict[str, Any], candidates: list[str], fallback: Any = "") -> Any:
    for candidate in candidates:
        if candidate in row:
            return row[candidate]
    return fallback


@dataclass
class ProcessActivityGraph:
    activity_id: int
    activity_name: str
    graph: nx.DiGraph
    seed_count: int = 0
    diagram: Optional[dict[str, Any]] = None
    extraction_warning: str = ""


def pg_build_package_map(t_package: pd.DataFrame) -> dict[int, dict[str, Any]]:
    package_map: dict[int, dict[str, Any]] = {}
    for _, row in t_package.iterrows():
        package_id = pg_to_int(row.get("Package_ID"))
        package_map[package_id] = {
            "id": package_id,
            "name": pg_clean_str(row.get("Name")),
            "parent_id": pg_to_int(row.get("Parent_ID")),
            "children": [],
        }
    for package_id, pkg in package_map.items():
        parent_id = pkg.get("parent_id", 0)
        if parent_id in package_map:
            package_map[parent_id]["children"].append(package_id)
    return package_map


def pg_package_path_name(package_id: int, package_map: dict[int, dict[str, Any]]) -> str:
    if package_id not in package_map:
        return f"Package {package_id}"
    parts: list[str] = []
    cur = package_id
    seen: set[int] = set()
    while cur and cur in package_map and cur not in seen:
        seen.add(cur)
        pkg = package_map[cur]
        parts.append(pkg.get("name") or f"Package {cur}")
        cur = pg_to_int(pkg.get("parent_id"))
    return " / ".join(reversed(parts))


def pg_normalize_path(value: str) -> str:
    return " / ".join(
        part for part in (" ".join(pg_clean_str(p).strip().lower().split()) for p in pg_clean_str(value).split("/")) if part
    )


def pg_find_package_ids_by_path(package_map: dict[int, dict[str, Any]], package_path: str) -> set[int]:
    wanted = pg_normalize_path(package_path)
    return {
        package_id
        for package_id in package_map
        if pg_normalize_path(pg_package_path_name(package_id, package_map)) == wanted
    }


def pg_expand_selected_packages(
    selected_ids: set[int],
    package_map: dict[int, dict[str, Any]],
    include_subpackages: bool = True,
) -> set[int]:
    out = set(selected_ids)
    if not include_subpackages:
        return out
    stack = list(selected_ids)
    while stack:
        package_id = stack.pop()
        for child in package_map.get(package_id, {}).get("children", []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def pg_build_object_index(
    t_object: pd.DataFrame,
    package_map: Optional[dict[int, dict[str, Any]]] = None,
) -> dict[int, dict[str, Any]]:
    package_map = package_map or {}
    object_index: dict[int, dict[str, Any]] = {}
    for _, row in t_object.iterrows():
        object_id = pg_to_int(row.get("Object_ID"))
        package_id = pg_to_int(row.get("Package_ID"))
        object_index[object_id] = {
            "object_id": object_id,
            "object_type": pg_clean_str(row.get("Object_Type")),
            "stereotype": pg_clean_str(row.get("Stereotype")),
            "stereotype_ex": pg_clean_str(row.get("StereotypeEx")),
            "parent_id": pg_to_int(row.get("ParentID")),
            "package_id": package_id,
            "package_path": pg_package_path_name(package_id, package_map),
            "label": pg_clean_str(row.get("Name")),

            "note": pg_clean_str(row.get("Note")),
            "classifier": pg_to_int(row.get("Classifier")),

        }
    return object_index


def pg_resolve_activity_id_for_object(
    obj_id: int,
    object_index: dict[int, dict[str, Any]],
    max_hops: int = 50,
) -> Optional[int]:
    cur = obj_id
    hops = 0
    seen: set[int] = set()
    while cur and hops < max_hops and cur not in seen:
        seen.add(cur)
        hops += 1
        obj = object_index.get(cur)
        if not obj:
            return None
        if obj.get("object_type") == "Activity":
            return cur
        cur = pg_to_int(obj.get("parent_id"))
    return None


def pg_is_activity_partition(obj: Optional[dict[str, Any]]) -> bool:
    return bool(obj and obj.get("object_type") == "ActivityPartition")


def pg_is_lane_or_pool_node(obj: Optional[dict[str, Any]]) -> bool:
    st = (
        pg_clean_str((obj or {}).get("stereotype"))
        + " "
        + pg_clean_str((obj or {}).get("stereotype_ex"))
    ).lower()
    return pg_is_activity_partition(obj) and ("lane" in st or "pool" in st)


def pg_resolve_lane_for_object(
    obj: Optional[dict[str, Any]],
    object_index: dict[int, dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if not obj:
        return None
    parent_obj = object_index.get(pg_to_int(obj.get("parent_id")))
    if not parent_obj or not pg_is_activity_partition(parent_obj):
        return None
    return {
        "lane_id": pg_to_int(parent_obj.get("object_id")),
        "lane_label": pg_clean_str(parent_obj.get("label")),
        "lane_stereotype": pg_clean_str(parent_obj.get("stereotype"))
        or pg_clean_str(parent_obj.get("stereotype_ex"))
        or "ActivityPartition",
    }


def pg_is_allowed_diagram_flow_node(obj: Optional[dict[str, Any]]) -> bool:
    if not obj:
        return False
    if obj.get("object_type") == "Activity":
        return False
    if pg_is_activity_partition(obj) or pg_is_lane_or_pool_node(obj):
        return False
    return obj.get("object_type") in ALLOWED_FLOW_NODE_TYPES


def pg_is_banned_object(obj: Optional[dict[str, Any]]) -> bool:
    return (
        obj is None
        or obj.get("object_type") in BANNED_OBJECT_TYPES
        or obj.get("stereotype") in BANNED_STEREOTYPES
    )


def pg_is_gateway_node(data: dict[str, Any]) -> bool:
    label = pg_clean_str(data.get("label"))
    return (
        data.get("stereotype") == "Gateway"
        and data.get("object_type") == "Decision"
        and (not label or "gateway" in label.lower())
    )


def pg_add_merged_edge(graph: nx.DiGraph, u: int, v: int, data: Optional[dict[str, Any]] = None) -> None:
    data = data or {}
    if u not in graph or v not in graph:
        return
    if graph.has_edge(u, v):
        existing = graph.edges[u, v]
        old_label = pg_clean_str(existing.get("label"))
        new_label = pg_clean_str(data.get("label"))
        if new_label and not old_label:
            existing["label"] = new_label
        elif new_label and old_label and new_label != old_label:
            existing["label"] = f"{old_label} / {new_label}"
        if data.get("connector_type") and not existing.get("connector_type"):
            existing["connector_type"] = data.get("connector_type")
        if data.get("connector_id") and not existing.get("connector_id"):
            existing["connector_id"] = data.get("connector_id")
    else:
        graph.add_edge(u, v, **data)


def pg_post_process_activity_graph(graph: nx.DiGraph) -> nx.DiGraph:
    for node, data in list(graph.nodes(data=True)):
        if node not in graph or not pg_is_gateway_node(data):
            continue
        predecessors = list(graph.predecessors(node))
        successors = list(graph.successors(node))
        for pred in predecessors:
            for succ in successors:
                if pred != succ:
                    pg_add_merged_edge(
                        graph,
                        pred,
                        succ,
                        {"label": "gateway_bypass", "connector_type": "synthetic"},
                    )
        graph.remove_node(node)

    for node, data in list(graph.nodes(data=True)):
        if node not in graph:
            continue
        if data.get("object_type") != "Event" and not pg_clean_str(data.get("label")):
            graph.remove_node(node)
        elif data.get("object_type") == "ActivityPartition":
            graph.remove_node(node)

    for node in list(graph.nodes()):
        if node in graph and graph.degree(node) == 0:
            graph.remove_node(node)
    return graph


def pg_build_connector_by_id(t_connector: pd.DataFrame) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for _, row in t_connector.iterrows():
        record = row.to_dict()
        connector_id = pg_to_int(record.get("Connector_ID"))
        if connector_id:
            out[connector_id] = record
    return out


def pg_df_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return [row.to_dict() for _, row in df.iterrows()]


def pg_build_diagram_indexes(
    t_diagram: pd.DataFrame,
    t_diagramobjects: pd.DataFrame,
    t_diagramlinks: pd.DataFrame,
) -> dict[str, dict[int, list[dict[str, Any]]]]:
    diagrams_by_parent: dict[int, list[dict[str, Any]]] = {}
    for row in pg_df_rows(t_diagram):
        diagram_id = pg_to_int(pg_pick_col(row, ["Diagram_ID", "DiagramID"], 0))
        parent_id = pg_to_int(pg_pick_col(row, ["ParentID", "Parent_ID", "ElementID", "Object_ID"], 0))
        if not diagram_id:
            continue
        item = {
            "diagram_id": diagram_id,
            "name": pg_clean_str(pg_pick_col(row, ["Name"], "")),
            "parent_id": parent_id,
            "raw": row,
        }
        diagrams_by_parent.setdefault(parent_id, []).append(item)
    for arr in diagrams_by_parent.values():
        arr.sort(key=lambda x: x["diagram_id"])

    diagram_objects_by_diagram: dict[int, list[dict[str, Any]]] = {}
    for row in pg_df_rows(t_diagramobjects):
        diagram_id = pg_to_int(pg_pick_col(row, ["Diagram_ID", "DiagramID"], 0))
        element_id = pg_to_int(pg_pick_col(row, ["Object_ID", "ElementID"], 0))
        if not diagram_id or not element_id:
            continue
        diagram_objects_by_diagram.setdefault(diagram_id, []).append(
            {"diagram_id": diagram_id, "element_id": element_id, "raw": row}
        )

    diagram_links_by_diagram: dict[int, list[dict[str, Any]]] = {}
    for row in pg_df_rows(t_diagramlinks):
        diagram_id = pg_to_int(pg_pick_col(row, ["DiagramID", "Diagram_ID"], 0))
        connector_id = pg_to_int(pg_pick_col(row, ["ConnectorID", "Connector_ID"], 0))
        if not diagram_id or not connector_id:
            continue
        hidden_raw = pg_pick_col(row, ["Hidden", "IsHidden"], 0)
        hidden = (
            hidden_raw is True
            or hidden_raw == 1
            or pg_clean_str(hidden_raw).lower() == "true"
            or pg_clean_str(hidden_raw) == "1"
        )
        diagram_links_by_diagram.setdefault(diagram_id, []).append(
            {
                "diagram_id": diagram_id,
                "connector_id": connector_id,
                "hidden": hidden,
                "raw": row,
            }
        )

    return {
        "diagrams_by_parent": diagrams_by_parent,
        "diagram_objects_by_diagram": diagram_objects_by_diagram,
        "diagram_links_by_diagram": diagram_links_by_diagram,
    }


def pg_find_main_diagram_for_activity(
    activity_id: int,
    activity_name: str,
    diagram_indexes: dict[str, dict[int, list[dict[str, Any]]]],
) -> Optional[dict[str, Any]]:
    diagrams = diagram_indexes["diagrams_by_parent"].get(activity_id, [])
    if not diagrams:
        return None
    same_name = next(
        (d for d in diagrams if pg_clean_str(d.get("name")) == pg_clean_str(activity_name)),
        None,
    )
    return same_name or diagrams[0]


def pg_build_activity_graph(
    activity_id: int,
    activity_name: str,
    object_index: dict[int, dict[str, Any]],
    connector_by_id: dict[int, dict[str, Any]],
    diagram_indexes: dict[str, dict[int, list[dict[str, Any]]]],
) -> ProcessActivityGraph:
    diagram = pg_find_main_diagram_for_activity(activity_id, activity_name, diagram_indexes)
    graph = nx.DiGraph(activity_id=activity_id, activity_name=activity_name)
    if not diagram:
        return ProcessActivityGraph(
            activity_id=activity_id,
            activity_name=activity_name,
            graph=graph,
            seed_count=0,
            diagram=None,
            extraction_warning="No child diagram found",
        )

    visible_element_ids: set[int] = set()
    diagram_id = pg_to_int(diagram.get("diagram_id"))
    diagram_objects = diagram_indexes["diagram_objects_by_diagram"].get(diagram_id, [])

    for dobj in diagram_objects:
        obj_id = pg_to_int(dobj.get("element_id"))
        obj = object_index.get(obj_id, {})
        if not pg_is_allowed_diagram_flow_node(obj):
            continue
        if pg_is_banned_object(obj):
            continue
        visible_element_ids.add(obj_id)
        lane = pg_resolve_lane_for_object(obj, object_index)
        graph.add_node(
            obj_id,
            id=pg_node_evidence_id(activity_id, obj_id),
            object_id=obj_id,
            label=obj.get("label", ""),
            normalized_label=pg_normalize_whitespace(obj.get("label", "")).lower(),
            object_type=obj.get("object_type", ""),
            stereotype=obj.get("stereotype", ""),
            lane=lane,
            parent_id=pg_to_int(obj.get("parent_id")),
            package_id=pg_to_int(obj.get("package_id")),
            classifier=pg_to_int(obj.get("classifier")),
            resolved_activity_id=pg_resolve_activity_id_for_object(obj_id, object_index) or activity_id,
            note_snippet=pg_safe_snippet(obj.get("note", ""), 400),
            activity_id=activity_id,
            diagram_id=diagram_id,
            diagram_name=diagram.get("name", ""),
        )

    diagram_links = diagram_indexes["diagram_links_by_diagram"].get(diagram_id, [])
    for link in diagram_links:
        if link.get("hidden"):
            continue
        connector_id = pg_to_int(link.get("connector_id"))
        row = connector_by_id.get(connector_id)
        if not row:
            continue
        start = pg_to_int(row.get("Start_Object_ID"))
        end = pg_to_int(row.get("End_Object_ID"))
        connector_type = pg_clean_str(row.get("Connector_Type"))
        if connector_type not in DIAGRAM_ALLOWED_CONNECTOR_TYPES:
            continue
        if start in visible_element_ids and end in visible_element_ids and start in graph and end in graph:
            pg_add_merged_edge(
                graph,
                start,
                end,
                {
                    "label": pg_clean_str(row.get("Name")),
                    "connector_type": connector_type,
                    "connector_id": connector_id,
                },
            )

    pg_post_process_activity_graph(graph)
    return ProcessActivityGraph(
        activity_id=activity_id,
        activity_name=activity_name,
        graph=graph,
        seed_count=len(visible_element_ids),
        diagram=diagram,
    )


def pg_package_summary(
    package_id: int,
    package_map: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    pkg = package_map.get(package_id, {})
    return {
        "package_id": package_id,
        "name": pkg.get("name", ""),
        "parent_id": pkg.get("parent_id", 0),
        "path": pg_package_path_name(package_id, package_map),
        "child_count": len(pkg.get("children", []) or []),
    }


class QEAAnalyzer:
    """
    AAroN-informed QEA File Analyzer.
    
    Every query function here is built with knowledge from AAroN's
    Java processors — it understands which columns matter, which
    implicit relationships exist, and how the tables connect.
    """
    
    # Open WebUI path aliases — resolve /mnt/data/ to actual mounts
    _PATH_ALIASES = [
        ("/mnt/data/", "/app/backend/data/uploads/"),
    ]
    _FALLBACK_DIRS = [
        "/app/backend/data/uploads",
        "/app/backend/data",
    ]
    
    @staticmethod
    def _resolve_path(qea_path: str = None) -> Path:
        """Resolve QEA file path with Open WebUI path alias awareness."""
        path = Path(qea_path)
        if path.exists():
            return path
        
        for alias, real in QEAAnalyzer._PATH_ALIASES:
            if qea_path.startswith(alias):
                remapped = Path(real) / qea_path[len(alias):]
                if remapped.exists():
                    return remapped
        
        filename = path.name
        for dir_path in QEAAnalyzer._FALLBACK_DIRS:
            candidate = Path(dir_path) / filename
            if candidate.exists():
                return candidate
        
        for dir_path in QEAAnalyzer._FALLBACK_DIRS:
            if not Path(dir_path).exists():
                continue
            for f in Path(dir_path).iterdir():
                if f.is_file() and f.name.endswith(f"_{filename}"):
                    return f
        
        raise FileNotFoundError(
            f"QEA file not found: {qea_path}\n"
            f"Searched: {qea_path}" +
            "".join(f"\n  - {Path(real) / qea_path[len(alias):]}" 
                     for alias, real in QEAAnalyzer._PATH_ALIASES 
                     if qea_path.startswith(alias)) +
            "".join(f"\n  - {dir_path}/{filename}"
                     for dir_path in QEAAnalyzer._FALLBACK_DIRS)
        )
    
    def __init__(self, qea_path: str = None):
        """Open a QEA file (SQLite database)."""
        self.qea_path = self._resolve_path(qea_path)
        self.conn = sqlite3.connect(str(self.qea_path))
        self.conn.row_factory = sqlite3.Row
        self._cache = {}
    
    def close(self):
        """Close the database connection."""
        self.conn.close()
    
    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a read-only query and return results as dicts."""
        c = self.conn.cursor()
        c.execute(sql, params)
        return [dict(row) for row in c.fetchall()]
    
    def _table_exists(self, table: str) -> bool:
        """Check if a table exists in the QEA file."""
        result = self._query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        return len(result) > 0
    
    # ── STRUCTURE DISCOVERY ────────────────────────────────
    
    def list_tables(self) -> list[str]:
        """List all tables in the QEA file."""
        rows = self._query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r['name'] for r in rows]
    
    def get_model_statistics(self) -> dict:
        """Get statistics about the model (AAroN-informed)."""
        stats = {}
        table_map = {
            "Packages": "t_package",
            "Elements": "t_object",
            "Connectors": "t_connector",
            "Diagrams": "t_diagram",
            "Attributes": "t_attribute",
            "Operations": "t_operation",
            "TaggedValues_Objects": "t_objectproperties",
            "TaggedValues_Connectors": "t_connectortag",
            "TaggedValues_Attributes": "t_attributetag",
            "CrossReferences": "t_xref",
        }
        for label, table in table_map.items():
            if self._table_exists(table):
                stats[label] = self._query(f"SELECT COUNT(*) as cnt FROM {table}")[0]['cnt']
        
        # Element types breakdown
        stats["ElementTypes"] = {}
        if self._table_exists("t_object"):
            types = self._query(
                "SELECT Object_Type, COUNT(*) as cnt FROM t_object "
                "GROUP BY Object_Type ORDER BY cnt DESC"
            )
            stats["ElementTypes"] = {r['Object_Type']: r['cnt'] for r in types}
        
        # Stereotypes breakdown
        stats["Stereotypes"] = {}
        if self._table_exists("t_object"):
            stereos = self._query(
                "SELECT Stereotype, COUNT(*) as cnt FROM t_object "
                "WHERE Stereotype IS NOT NULL AND Stereotype != '' "
                "GROUP BY Stereotype ORDER BY cnt DESC"
            )
            stats["Stereotypes"] = {r['Stereotype']: r['cnt'] for r in stereos}
        
        return stats
    
    def get_package_tree(self) -> dict:
        """
        Get the full package hierarchy.
        
        Package hierarchy is from t_package (EAPackage.java):
        - Package_ID, Name, Parent_ID, ea_guid, Notes, CreatedDate, ModifiedDate
        
        Root packages have Parent_ID = 0 or NULL.
        Uses AAroN's knowledge: Package_ID is the primary join key.
        """
        packages = self._query(
            "SELECT Package_ID, Name, Parent_ID, ea_guid, Notes, "
            "CreatedDate, ModifiedDate, Version "
            "FROM t_package ORDER BY Parent_ID, Name"
        )
        
        # Build tree
        by_id = {}
        roots = []
        for p in packages:
            pid = p['Package_ID']
            node = {
                "name": p['Name'],
                "id": pid,
                "ea_guid": p['ea_guid'],
                "notes": p['Notes'],
                "version": p['Version'],
                "created": p['CreatedDate'],
                "modified": p['ModifiedDate'],
                "children": [],
                "element_count": self._count_elements_in_package(pid)
            }
            by_id[pid] = node
        
        for p in packages:
            pid = p['Package_ID']
            parent_id = p['Parent_ID']
            if parent_id and parent_id != 0 and parent_id in by_id:
                by_id[parent_id]["children"].append(by_id[pid])
            else:
                roots.append(by_id[pid])
        
        return {"roots": roots, "total_packages": len(packages)}
    
    def _count_elements_in_package(self, package_id: int) -> int:
        """Count elements directly in a package (AAroN: Package_ID in t_object)."""
        r = self._query(
            "SELECT COUNT(*) as cnt FROM t_object WHERE Package_ID = ?",
            (package_id,)
        )
        return r[0]['cnt'] if r else 0
    
    def list_object_types(self) -> list[dict]:
        """List all Object_Type values with counts."""
        return self._query(
            "SELECT Object_Type, COUNT(*) as count FROM t_object "
            "GROUP BY Object_Type ORDER BY count DESC"
        )
    
    def list_stereotypes(self) -> list[dict]:
        """List all stereotypes with counts."""
        return self._query(
            "SELECT Stereotype, Object_Type, COUNT(*) as count FROM t_object "
            "WHERE Stereotype IS NOT NULL AND Stereotype != '' "
            "GROUP BY Stereotype, Object_Type ORDER BY count DESC"
        )
    
    def get_diagrams(self) -> list[dict]:
        """
        Get all diagrams with their element counts.
        From AAroN: t_diagram has Diagram_ID, Name, Diagram_Type, Package_ID, ea_guid, Author, Notes, etc.
        """
        return self._query("""
            SELECT d.Diagram_ID, d.Name, d.Diagram_Type, d.Package_ID,
                   d.ea_guid, d.Author, d.Version, d.Notes,
                   d.CreatedDate, d.ModifiedDate, d.Stereotype,
                   p.Name as Package_Name,
                   (SELECT COUNT(*) FROM t_diagramobjects d2 WHERE d2.Diagram_ID = d.Diagram_ID) as object_count
            FROM t_diagram d
            LEFT JOIN t_package p ON d.Package_ID = p.Package_ID
            ORDER BY p.Name, d.Name
        """)
    
    # ── ELEMENT QUERIES (AAroN's ObjectProcessor logic) ────
    
    def find_elements(
        self,
        name: str = None,
        object_type: str = None,
        stereotype: str = None,
        package_id: int = None,
        status: str = None,
        limit: int = 200
    ) -> list[dict]:
        """
        Find elements by various criteria.
        Maps directly to AAroN's EAObject columns.
        """
        conditions = []
        params = []
        
        if name:
            conditions.append("o.Name LIKE ?")
            params.append(f"%{name}%")
        if object_type:
            conditions.append("o.Object_Type = ?")
            params.append(object_type)
        if stereotype:
            conditions.append("o.Stereotype LIKE ?")
            params.append(f"%{stereotype}%")
        if package_id is not None:
            conditions.append("o.Package_ID = ?")
            params.append(package_id)
        if status:
            conditions.append("o.Status = ?")
            params.append(status)
        
        where = " AND ".join(conditions) if conditions else "1=1"
        
        return self._query(f"""
            SELECT o.Object_ID, o.Object_Type, o.Name, o.Stereotype,
                   o.ea_guid, o.Package_ID, o.ParentID, o.Author,
                   o.Status, o.Phase, o.Version, o.Complexity,
                   o.CreatedDate, o.ModifiedDate, o.Note,
                   o.Classifier_guid, o.Abstract, o.Scope,
                   o.PDATA1, o.PDATA2, o.PDATA3,
                   p.Name as Package_Name
            FROM t_object o
            LEFT JOIN t_package p ON o.Package_ID = p.Package_ID
            WHERE {where}
            ORDER BY o.Object_Type, o.Name
            LIMIT ?
        """, tuple(params) + (limit,))
    
    def get_element_detail(self, element_id: int) -> dict:
        """
        Get full detail for one element — the AAroN ObjectProcessor way.
        Includes all relevant columns, tagged values, attributes,
        operations, and both incoming and outgoing relationships.
        """
        # Core element data (all EAObject columns that AAroN maps)
        element = self._query("""
            SELECT o.*, p.Name as Package_Name
            FROM t_object o
            LEFT JOIN t_package p ON o.Package_ID = p.Package_ID
            WHERE o.Object_ID = ?
        """, (element_id,))
        
        if not element:
            return {"error": f"Element {element_id} not found"}
        
        result = dict(element[0])
        
        # Tagged Values (t_objectproperties — AAroN TaggedValueHelper)
        result["tagged_values"] = self._query(
            "SELECT PropertyID, Property, Value, Notes, ea_guid "
            "FROM t_objectproperties WHERE Object_ID = ? ORDER BY Property",
            (element_id,)
        )
        
        # Attributes (t_attribute — AAroN AttributeProcessor)
        result["attributes"] = self._query(
            "SELECT ID, Name, Type, Stereotype, Scope, Visibility, "
            "Notes, ea_guid, LowerBound, UpperBound, IsStatic, "
            "IsOrdered, IsCollection, AllowDuplicates "
            "FROM t_attribute WHERE Object_ID = ? ORDER BY Pos",
            (element_id,)
        )
        
        # Operations (t_operation — AAroN OperationProcessor)
        result["operations"] = self._query(
            "SELECT OperationID, Name, Type, Scope, Stereotype, "
            "Notes, ea_guid, IsStatic, Abstract, IsQuery "
            "FROM t_operation WHERE Object_ID = ? ORDER BY Pos",
            (element_id,)
        )
        
        # Relationships — incoming and outgoing
        result["outgoing_relationships"] = self._query("""
            SELECT c.Connector_ID, c.Name, c.Connector_Type, c.Stereotype,
                   c.Direction, c.Notes, c.ea_guid,
                   c.End_Object_ID as target_id,
                   o2.Name as target_name, o2.Object_Type as target_type,
                   o2.Stereotype as target_stereotype,
                   c.SourceRole, c.DestRole,
                   c.SourceCard, c.DestCard
            FROM t_connector c
            JOIN t_object o2 ON c.End_Object_ID = o2.Object_ID
            WHERE c.Start_Object_ID = ?
            ORDER BY c.Connector_Type, o2.Name
        """, (element_id,))
        
        result["incoming_relationships"] = self._query("""
            SELECT c.Connector_ID, c.Name, c.Connector_Type, c.Stereotype,
                   c.Direction, c.Notes, c.ea_guid,
                   c.Start_Object_ID as source_id,
                   o2.Name as source_name, o2.Object_Type as source_type,
                   o2.Stereotype as source_stereotype,
                   c.SourceRole, c.DestRole,
                   c.SourceCard, c.DestCard
            FROM t_connector c
            JOIN t_object o2 ON c.Start_Object_ID = o2.Object_ID
            WHERE c.End_Object_ID = ?
            ORDER BY c.Connector_Type, o2.Name
        """, (element_id,))
        
        # Implicit relationships (AAroN-discovered from ObjectProcessor)
        result["implicit_relationships"] = self._get_implicit_relationships(element[0])
        
        # Diagrams containing this element
        result["diagrams"] = self._query("""
            SELECT d.Diagram_ID, d.Name, d.Diagram_Type,
                   do.Sequence, do.RectTop, do.RectLeft
            FROM t_diagramobjects do
            JOIN t_diagram d ON do.Diagram_ID = d.Diagram_ID
            WHERE do.Object_ID = ?
            ORDER BY d.Name
        """, (element_id,))
        
        # Cross-references (t_xref — AAroN XRefProcessor)
        result["cross_references"] = self._query(
            "SELECT XrefID, Name, Type, Description, Client, Supplier, "
            "Behavior, Visibility, Partition "
            "FROM t_xref WHERE Client LIKE ?",
            (f"%{result.get('ea_guid', '')}%",)
        )
        
        return result
    
    def _get_implicit_relationships(self, element: dict) -> list[dict]:
        """
        Discover implicit relationships AAroN finds in ObjectProcessor.
        
        These are NOT stored in t_connector — they're derived from
        t_object columns (PDATA1, PDATA3, ParentID, Classifier_guid).
        """
        implicit = []
        object_type = element.get('Object_Type', '')
        ea_guid = element.get('ea_guid', '')
        object_id = element.get('Object_ID')
        
        # CONTAINS: Package → Object (AAroN emits this for EVERY object via Package_ID)
        package_id = element.get('Package_ID')
        if package_id:
            pkg = self._query(
                "SELECT Package_ID, Name FROM t_package WHERE Package_ID = ?",
                (package_id,)
            )
            if pkg:
                implicit.append({
                    "type": "CONTAINS",
                    "direction": "incoming",
                    "parent_name": pkg[0]['Name'],
                    "parent_id": pkg[0]['Package_ID'],
                    "source_column": "Package_ID"
                })
        
        # INSTANCE_OF: Object/Part/Port → PDATA1 as GUID (classifier)
        if object_type in ('Object', 'Part', 'Port'):
            pdata1 = element.get('PDATA1', '')
            if pdata1 and self._is_guid(pdata1):
                ref = self._find_by_guid(pdata1)
                if ref:
                    implicit.append({
                        "type": "INSTANCE_OF",
                        "target": ref['Name'],
                        "target_id": ref['Object_ID'],
                        "target_type": ref['Object_Type'],
                        "source_column": "PDATA1"
                    })
        
        # CLASSIFIER: Object/Action → Classifier_guid
        # AAroN requires a valid EA GUID (isEaGuid) before creating the edge.
        if object_type in ('Object', 'Action'):
            cguid = element.get('Classifier_guid', '')
            if cguid and self._is_guid(cguid):
                ref = self._find_by_guid(cguid)
                if ref:
                    implicit.append({
                        "type": "CLASSIFIER",
                        "target": ref['Name'],
                        "target_id": ref['Object_ID'],
                        "target_type": ref['Object_Type'],
                        "source_column": "Classifier_guid"
                    })
        
        # BEHAVIOUR: Action → PDATA1 as GUID (behavioural element)
        if object_type == 'Action':
            pdata1 = element.get('PDATA1', '')
            if pdata1 and self._is_guid(pdata1):
                ref = self._find_by_guid(pdata1)
                if ref:
                    implicit.append({
                        "type": "BEHAVIOUR",
                        "target": ref['Name'],
                        "target_id": ref['Object_ID'],
                        "source_column": "PDATA1"
                    })
        
        # REUSAGE: Part/Port → PDATA3
        if object_type in ('Part', 'Port'):
            pdata3 = element.get('PDATA3', '')
            if pdata3 and self._is_guid(pdata3):
                ref = self._find_by_guid(pdata3)
                if ref:
                    implicit.append({
                        "type": "REUSAGE",
                        "target": ref['Name'],
                        "target_id": ref['Object_ID'],
                        "source_column": "PDATA3"
                    })
        
        # HAS_PORT / HAS_PART / EMBEDS / HAS_PARENT: ParentID → Object_ID
        # Matches AAroN ObjectProcessor exactly: within the parentId>0 block,
        # HAS_PORT (Port only) and HAS_PART (Part only) are emitted IN ADDITION
        # to EMBEDS and HAS_PARENT, which AAroN emits UNCONDITIONALLY for every
        # parented object (not mutually exclusive). A Port therefore yields
        # HAS_PORT + EMBEDS + HAS_PARENT.
        parent_id = element.get('ParentID')
        if parent_id and parent_id > 0:
            parent = self._query(
                "SELECT Object_ID, Name, Object_Type, Stereotype "
                "FROM t_object WHERE Object_ID = ?",
                (parent_id,)
            )
            if parent:
                p = parent[0]
                # HAS_PORT — only for Ports (parent → port)
                if object_type == 'Port':
                    implicit.append({
                        "type": "HAS_PORT",
                        "direction": "incoming",
                        "parent_name": p['Name'],
                        "parent_id": p['Object_ID'],
                        "source_column": "ParentID"
                    })
                # HAS_PART — only for Parts (parent → part)
                elif object_type == 'Part':
                    implicit.append({
                        "type": "HAS_PART",
                        "direction": "incoming",
                        "parent_name": p['Name'],
                        "parent_id": p['Object_ID'],
                        "source_column": "ParentID"
                    })
                # EMBEDS — ALWAYS for any parented object (parent → child)
                implicit.append({
                    "type": "EMBEDS",
                    "direction": "incoming",
                    "parent_name": p['Name'],
                    "parent_id": p['Object_ID'],
                    "source_column": "ParentID"
                })
                # HAS_PARENT — ALWAYS, inverse edge (child → parent)
                implicit.append({
                    "type": "HAS_PARENT",
                    "direction": "outgoing",
                    "parent_name": p['Name'],
                    "parent_id": p['Object_ID'],
                    "source_column": "ParentID"
                })
        
        return implicit
    
    def _is_guid(self, val: str) -> bool:
        """Check if a value is a valid Sparx EA GUID.

        Mirrors AAroN's GUIDHelper.guidPattern exactly:
        {8-4-4-4-12} hex digits. A loose pattern would create spurious
        implicit relationships from malformed PDATA fields, so we keep
        the strict form to stay faithful to AAroN.
        """
        if not val:
            return False
        return bool(re.match(
            r'^\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-'
            r'[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$',
            val
        ))
    
    def _find_by_guid(self, guid: str) -> dict:
        """Find an element by its ea_guid."""
        clean = guid.strip('{}')
        results = self._query(
            "SELECT Object_ID, Name, Object_Type, Stereotype, ea_guid "
            "FROM t_object WHERE ea_guid LIKE ?",
            (f"%{clean}%",)
        )
        return results[0] if results else None
    
    def search_elements(self, query: str, limit: int = 50) -> list[dict]:
        """
        Full-text search across element names, notes, and aliases.
        Searches both t_object and t_package.
        """
        like = f"%{query}%"
        return self._query("""
            SELECT Object_ID, Object_Type, Name, Stereotype,
                   ea_guid, Note, Package_ID, Status, Phase,
                   't_object' as source_table
            FROM t_object
            WHERE Name LIKE ? OR Note LIKE ? OR Alias LIKE ?
            UNION ALL
            SELECT Package_ID as Object_ID, 'Package' as Object_Type,
                   Name, '' as Stereotype, ea_guid, Notes as Note,
                   Parent_ID as Package_ID, '' as Status, '' as Phase,
                   't_package' as source_table
            FROM t_package
            WHERE Name LIKE ? OR Notes LIKE ?
            ORDER BY Name
            LIMIT ?
        """, (like, like, like, like, like, limit))
    
    # ── RELATIONSHIP QUERIES (AAroN's ConnectorProcessor logic) ──
    
    def get_relationships(
        self,
        element_id: int = None,
        connector_type: str = None,
        stereotype: str = None,
        limit: int = 200
    ) -> list[dict]:
        """
        Get relationships with full AAroN connector details.
        Maps to AAroN's ConnectorProcessor which reads ALL EAConnector columns.
        """
        conditions = []
        params = []
        
        if element_id is not None:
            conditions.append(
                "(c.Start_Object_ID = ? OR c.End_Object_ID = ?)"
            )
            params.extend([element_id, element_id])
        if connector_type:
            conditions.append("c.Connector_Type = ?")
            params.append(connector_type)
        if stereotype:
            conditions.append("c.Stereotype LIKE ?")
            params.append(f"%{stereotype}%")
        
        where = " AND ".join(conditions) if conditions else "1=1"
        
        return self._query(f"""
            SELECT c.Connector_ID, c.Name, c.Connector_Type, c.Stereotype,
                   CASE
                       WHEN c.Stereotype IS NOT NULL AND TRIM(c.Stereotype) != ''
                       THEN c.Stereotype
                       ELSE c.Connector_Type
                   END as Effective_Type,
                   c.Direction, c.Notes, c.ea_guid,
                   c.Start_Object_ID, o1.Name as Source_Name,
                   o1.Object_Type as Source_Type, o1.Stereotype as Source_Stereotype,
                   c.End_Object_ID, o2.Name as Target_Name,
                   o2.Object_Type as Target_Type, o2.Stereotype as Target_Stereotype,
                   c.SourceRole, c.DestRole,
                   c.SourceCard, c.DestCard,
                   c.SourceIsAggregate, c.DestIsAggregate,
                   c.SourceIsNavigable, c.DestIsNavigable,
                   c.SourceContainment, c.DestContainment,
                   c.VirtualInheritance, c.LinkAccess,
                   d.Name as Diagram_Name
            FROM t_connector c
            JOIN t_object o1 ON c.Start_Object_ID = o1.Object_ID
            JOIN t_object o2 ON c.End_Object_ID = o2.Object_ID
            LEFT JOIN t_diagram d ON c.DiagramID = d.Diagram_ID
            WHERE {where}
            ORDER BY c.Connector_Type, o1.Name
            LIMIT ?
        """, tuple(params) + (limit,))
    
    def find_relationship_path(
        self,
        start_id: int,
        end_id: int,
        max_depth: int = 5
    ) -> list[dict]:
        """
        Find paths between two elements through t_connector.
        Uses iterative BFS (not recursive — SQLite limitation).
        """
        visited = {start_id}
        # BFS queue: (current_id, path)
        queue = [(start_id, [])]
        
        for _ in range(max_depth):
            next_queue = []
            for curr_id, path in queue:
                # Find all connected elements
                neighbors = self._query("""
                    SELECT 
                        CASE WHEN Start_Object_ID = ? THEN End_Object_ID 
                             ELSE Start_Object_ID END as neighbor_id,
                        Connector_ID, Name, Connector_Type, Stereotype,
                        Start_Object_ID, End_Object_ID
                    FROM t_connector
                    WHERE Start_Object_ID = ? OR End_Object_ID = ?
                """, (curr_id, curr_id, curr_id))
                
                for n in neighbors:
                    neighbor = n['neighbor_id']
                    if neighbor == end_id:
                        # Found path!
                        full_path = path + [{
                            "from_id": n['Start_Object_ID'],
                            "to_id": n['End_Object_ID'],
                            "connector_id": n['Connector_ID'],
                            "name": n['Name'],
                            "type": n['Connector_Type'],
                            "stereotype": n['Stereotype'],
                        }]
                        # Resolve names
                        for step in full_path:
                            step['from_name'] = self._get_object_name(step['from_id'])
                            step['to_name'] = self._get_object_name(step['to_id'])
                        return full_path
                    
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_queue.append((
                            neighbor,
                            path + [{
                                "from_id": n['Start_Object_ID'],
                                "to_id": n['End_Object_ID'],
                                "connector_id": n['Connector_ID'],
                                "name": n['Name'],
                                "type": n['Connector_Type'],
                                "stereotype": n['Stereotype'],
                            }]
                        ))
            queue = next_queue
        
        return []  # No path found within max_depth
    
    def _get_object_name(self, object_id: int) -> str:
        r = self._query(
            "SELECT Name FROM t_object WHERE Object_ID = ?",
            (object_id,)
        )
        return r[0]['Name'] if r else f"ID:{object_id}"
    
    # ── TAGGED VALUES (NAF-CRITICAL — AAroN's TaggedValueHelper) ──
    
    def get_tagged_values(self, element_id: int) -> dict:
        """
        Get all tagged values for an element.
        In NAF architectures, these carry critical metadata
        (e.g., operational attributes, capability measures, standards).
        
        AAroN processes these via TaggedValueHelper — either as
        properties on the element (AS_PROPERTY mode) or as
        separate nodes (AS_NODE mode).
        """
        # Object tagged values
        obj_tags = self._query(
            "SELECT PropertyID, Property, Value, Notes, ea_guid "
            "FROM t_objectproperties WHERE Object_ID = ? ORDER BY Property",
            (element_id,)
        )
        
        # Also check connector tags if element has connectors
        conn_tags = self._query("""
            SELECT ct.PropertyID, ct.Property, ct.VALUE as Value,
                   ct.NOTES as Notes, ct.ea_guid,
                   c.Connector_ID, c.Name as Connector_Name
            FROM t_connectortag ct
            JOIN t_connector c ON ct.ElementID = c.Connector_ID
            WHERE c.Start_Object_ID = ? OR c.End_Object_ID = ?
            ORDER BY ct.Property
        """, (element_id, element_id))
        
        return {
            "element_tags": obj_tags,
            "connector_tags": conn_tags,
        }
    
    def find_elements_by_tag(
        self,
        tag_name: str,
        tag_value: str = None,
        limit: int = 200
    ) -> list[dict]:
        """
        Find elements by their tagged values.
        CRITICAL for NAF: e.g., find all elements with 
        tag 'OperationalActivity' or 'SecurityClassification'.
        
        Searches t_objectproperties (AAroN: EAObjectProperty table).
        """
        if tag_value:
            return self._query("""
                SELECT o.Object_ID, o.Name, o.Object_Type, o.Stereotype,
                       o.ea_guid, o.Package_ID,
                       op.Property, op.Value, op.Notes
                FROM t_objectproperties op
                JOIN t_object o ON op.Object_ID = o.Object_ID
                WHERE op.Property = ? AND op.Value LIKE ?
                ORDER BY o.Object_Type, o.Name
                LIMIT ?
            """, (tag_name, f"%{tag_value}%", limit))
        else:
            return self._query("""
                SELECT o.Object_ID, o.Name, o.Object_Type, o.Stereotype,
                       o.ea_guid, o.Package_ID,
                       op.Property, op.Value, op.Notes
                FROM t_objectproperties op
                JOIN t_object o ON op.Object_ID = o.Object_ID
                WHERE op.Property = ?
                ORDER BY o.Object_Type, o.Name
                LIMIT ?
            """, (tag_name, limit))
    
    def list_all_tag_names(self) -> list[dict]:
        """List all unique tagged value property names with counts."""
        return self._query("""
            SELECT Property, COUNT(*) as usage_count,
                   COUNT(DISTINCT Object_ID) as element_count
            FROM t_objectproperties
            GROUP BY Property
            ORDER BY usage_count DESC
        """)
    
    # ── NAF-SPECIFIC VIEWS ──────────────────────────────────
    
    def get_naf_view_elements(self, view_type: str) -> list[dict]:
        """
        Get elements belonging to a specific NAF view.
        Uses stereotype matching from NAF_VIEW_STEREOTYPES mapping.
        """
        stereotypes = NAF_VIEW_STEREOTYPES.get(view_type.upper(), [view_type])
        placeholders = ",".join(["?" for _ in stereotypes])
        
        return self._query(f"""
            SELECT o.Object_ID, o.Name, o.Object_Type, o.Stereotype,
                   o.ea_guid, o.Package_ID, o.Note, o.Status, o.Phase,
                   p.Name as Package_Name
            FROM t_object o
            LEFT JOIN t_package p ON o.Package_ID = p.Package_ID
            WHERE o.Stereotype IN ({placeholders})
            ORDER BY o.Object_Type, o.Name
        """, tuple(stereotypes))
    
    def get_capability_hierarchy(self) -> list[dict]:
        """
        NAF-3: Get capability composition hierarchy.
        Finds elements with Capability stereotype and their
        composition/aggregation relationships.
        """
        capabilities = self._query("""
            SELECT o.Object_ID, o.Name, o.Note, o.ea_guid,
                   o.Status, o.Phase, o.Stereotype
            FROM t_object o
            WHERE o.Stereotype LIKE '%Capability%'
            ORDER BY o.Name
        """)
        
        result = []
        for cap in capabilities:
            # Find sub-capabilities via Composition/Aggregation connectors
            sub_caps = self._query("""
                SELECT o2.Object_ID, o2.Name, o2.Stereotype,
                       c.Connector_Type, c.Name as Relationship_Name
                FROM t_connector c
                JOIN t_object o2 ON c.End_Object_ID = o2.Object_ID
                WHERE c.Start_Object_ID = ?
                  AND (c.Connector_Type IN ('Composition', 'Aggregation', 'Generalization'))
                  AND o2.Stereotype LIKE '%Capability%'
            """, (cap['Object_ID'],))
            
            cap['sub_capabilities'] = sub_caps
            result.append(cap)
        
        return result
    
    def get_information_flows(self) -> list[dict]:
        """
        NAF-2/NAF-6: Get information exchanges/flows.
        Uses AAroN's XRefProcessor knowledge: conveyed items
        are in t_xref with Behavior='conveyed'.
        """
        # Connectors typed as InformationFlow
        flows = self._query("""
            SELECT c.Connector_ID, c.Name, c.Connector_Type, c.Stereotype,
                   c.Notes, c.ea_guid,
                   o1.Name as Source_Name, o1.Object_Type as Source_Type,
                   o2.Name as Target_Name, o2.Object_Type as Target_Type,
                   c.SourceCard, c.DestCard
            FROM t_connector c
            JOIN t_object o1 ON c.Start_Object_ID = o1.Object_ID
            JOIN t_object o2 ON c.End_Object_ID = o2.Object_ID
            WHERE c.Connector_Type = 'InformationFlow'
               OR c.Stereotype LIKE '%InformationFlow%'
               OR c.Stereotype LIKE '%Needline%'
            ORDER BY o1.Name
        """)
        
        # For each flow, try to find conveyed items via t_xref
        for flow in flows:
            conveyed = self._query("""
                SELECT Description, Behavior, Client, Supplier
                FROM t_xref
                WHERE Name = 'MOFProps' AND Behavior = 'conveyed'
                  AND Client LIKE ?
            """, (f"%{flow['ea_guid']}%",))
            flow['conveyed_items_xref'] = conveyed
        
        return flows
    
    # ── RAW SQL FOR ADVANCED QUERIES ───────────────────────
    
    def execute_query(self, sql: str, limit: int = 200) -> list[dict]:
        """
        Execute a read-only SQL query for advanced analysis.
        The LLM can use this with AAroN-informed SQL knowledge.
        
        SAFETY: Only SELECT statements allowed.
        """
        sql_stripped = sql.strip().upper()
        if not sql_stripped.startswith("SELECT"):
            return [{"error": "Only SELECT queries allowed"}]
        
        # Add LIMIT if not present (safety)
        if "LIMIT" not in sql_stripped:
            sql = sql.rstrip(";") + f" LIMIT {limit}"
        
        try:
            return self._query(sql)
        except sqlite3.Error as e:
            return [{"error": str(e), "sql": sql}]
    
    def get_table_schema(self, table_name: str) -> list[dict]:
        """Get the schema (column names and types) for any table."""
        return self._query(f"PRAGMA table_info({table_name})")
    
    # ── ADVANCED: DIAGRAM ANALYSIS ─────────────────────────
    
    def get_diagram_content(self, diagram_id: int) -> dict:
        """
        Get all objects and connectors on a diagram.
        Uses AAroN's knowledge:
        - t_diagramobjects maps Object_ID → Diagram_ID with position
        - t_diagramlinks maps Connector_ID → DiagramID with geometry
        """
        diagram = self._query(
            "SELECT * FROM t_diagram WHERE Diagram_ID = ?",
            (diagram_id,)
        )
        if not diagram:
            return {"error": f"Diagram {diagram_id} not found"}
        
        result = dict(diagram[0])
        
        # Objects on diagram with position
        result["objects"] = self._query("""
            SELECT do.Diagram_ID, do.Object_ID, do.RectTop, do.RectLeft,
                   do.RectRight, do.RectBottom, do.Sequence, do.ObjectStyle,
                   o.Name, o.Object_Type, o.Stereotype, o.ea_guid
            FROM t_diagramobjects do
            JOIN t_object o ON do.Object_ID = o.Object_ID
            WHERE do.Diagram_ID = ?
            ORDER BY do.Sequence
        """, (diagram_id,))
        
        # Connectors on diagram
        result["connectors"] = self._query("""
            SELECT dl.ConnectorID, dl.Geometry, dl.Style, dl.Hidden,
                   c.Name, c.Connector_Type, c.Stereotype, c.ea_guid,
                   o1.Name as Source_Name, o2.Name as Target_Name
            FROM t_diagramlinks dl
            JOIN t_connector c ON dl.ConnectorID = c.Connector_ID
            JOIN t_object o1 ON c.Start_Object_ID = o1.Object_ID
            JOIN t_object o2 ON c.End_Object_ID = o2.Object_ID
            WHERE dl.DiagramID = ?
        """, (diagram_id,))
        
        return result

    # ── PROCESS DISCOVERY & EXTRACTION (DIAGRAM-BASED) ─────

    def _read_table_df(self, table_name: str) -> pd.DataFrame:
        if not self._table_exists(table_name):
            return pd.DataFrame()
        return pd.read_sql(f"SELECT * FROM {table_name}", self.conn)

    def _read_process_tables(self) -> dict[str, pd.DataFrame]:
        return {
            "t_object": self._read_table_df("t_object"),
            "t_connector": self._read_table_df("t_connector"),
            "t_package": self._read_table_df("t_package"),
            "t_diagram": self._read_table_df("t_diagram"),
            "t_diagramobjects": self._read_table_df("t_diagramobjects"),
            "t_diagramlinks": self._read_table_df("t_diagramlinks"),
        }

    def list_process_packages_and_activities(
        self,
        package_path: str = "",
        include_subpackages: bool = True,
        include_empty_packages: bool = True,
    ) -> dict[str, Any]:
        """
        Discovery endpoint for process extraction workflows.

        Returns compact package summaries and Activity objects so callers can
        select activity IDs before requesting extracted process graphs.
        """
        tables = self._read_process_tables()
        t_package = tables["t_package"]
        t_object = tables["t_object"]

        if t_package.empty:
            raise ValueError("Missing or empty t_package table")
        if t_object.empty:
            raise ValueError("Missing or empty t_object table")

        package_map = pg_build_package_map(t_package)

        if package_path:
            selected_package_ids = pg_find_package_ids_by_path(package_map, package_path)
            if not selected_package_ids:
                raise ValueError(f'Package path not found: "{package_path}"')
            scoped_package_ids = pg_expand_selected_packages(
                selected_package_ids,
                package_map,
                include_subpackages=include_subpackages,
            )
        else:
            scoped_package_ids = set(package_map.keys())

        activities: list[dict[str, Any]] = []
        for _, row in t_object.iterrows():
            if pg_clean_str(row.get("Object_Type")) != "Activity":
                continue

            package_id = pg_to_int(row.get("Package_ID"))
            if package_id not in scoped_package_ids:
                continue

            activity_id = pg_to_int(row.get("Object_ID"))
            activities.append(
                {
                    "activity_id": activity_id,
                    "activity_name": pg_clean_str(row.get("Name")),
                    "package_id": package_id,
                    "package_path": pg_package_path_name(package_id, package_map),
                }
            )

        activities.sort(
            key=lambda x: (
                str(x.get("package_path", "")).lower(),
                str(x.get("activity_name", "")).lower(),
                int(x.get("activity_id", 0)),
            )
        )

        activity_package_ids = {a["package_id"] for a in activities}
        visible_package_ids = scoped_package_ids if include_empty_packages else activity_package_ids

        packages = [
            pg_package_summary(package_id, package_map)
            for package_id in sorted(visible_package_ids)
            if package_id in package_map
        ]
        packages.sort(key=lambda x: str(x.get("path", "")).lower())

        return {
            "database_file": str(self.qea_path),
            "package_path_filter": package_path,
            "include_subpackages": include_subpackages,
            "package_count": len(packages),
            "activity_count": len(activities),
            "packages": packages,
            "activities": activities,
        }

    def extract_operational_activity_graphs(
        self,
        package_path: str = "",
        include_subpackages: bool = True,
    ) -> list[ProcessActivityGraph]:
        """
        Build operational Activity process graphs from diagram tables.
        """
        tables = self._read_process_tables()
        required = [
            "t_object",
            "t_connector",
            "t_package",
            "t_diagram",
            "t_diagramobjects",
            "t_diagramlinks",
        ]
        missing = [name for name in required if tables[name].empty]
        if missing:
            raise ValueError("Missing or empty required EA tables for diagram extraction: " + ", ".join(missing))

        package_map = pg_build_package_map(tables["t_package"])
        if package_path:
            selected = pg_find_package_ids_by_path(package_map, package_path)
            if not selected:
                raise ValueError(f'Package path not found: "{package_path}"')
            allowed_package_ids = pg_expand_selected_packages(
                selected,
                package_map,
                include_subpackages=include_subpackages,
            )
        else:
            allowed_package_ids = set(package_map.keys())

        object_index = pg_build_object_index(tables["t_object"], package_map)
        connector_by_id = pg_build_connector_by_id(tables["t_connector"])
        diagram_indexes = pg_build_diagram_indexes(
            tables["t_diagram"],
            tables["t_diagramobjects"],
            tables["t_diagramlinks"],
        )

        activities: list[tuple[int, str]] = []
        for obj_id, obj in object_index.items():
            if obj.get("object_type") != "Activity":
                continue
            if pg_to_int(obj.get("package_id")) not in allowed_package_ids:
                continue
            activities.append((obj_id, obj.get("label") or f"Activity {obj_id}"))
        activities.sort(key=lambda x: x[1])

        activity_graphs: list[ProcessActivityGraph] = []
        for activity_id, activity_name in activities:
            ag = pg_build_activity_graph(
                activity_id,
                activity_name,
                object_index,
                connector_by_id,
                diagram_indexes,
            )
            if ag.graph.number_of_nodes() > 0:
                activity_graphs.append(ag)

        return activity_graphs

    def summarize_extracted_activity_graphs(
        self,
        package_path: str = "",
        include_subpackages: bool = True,
        max_items: int = 500,
    ) -> dict[str, Any]:
        max_items = max(1, min(int(max_items), 2000))
        activity_graphs = self.extract_operational_activity_graphs(
            package_path=package_path,
            include_subpackages=include_subpackages,
        )

        summaries = [
            {
                "activity_id": ag.activity_id,
                "activity_name": ag.activity_name,
                "nodes": ag.graph.number_of_nodes(),
                "edges": ag.graph.number_of_edges(),
                "seed_count": ag.seed_count,
                "diagram_id": (ag.diagram or {}).get("diagram_id"),
                "diagram_name": (ag.diagram or {}).get("name"),
                "extraction_warning": ag.extraction_warning,
            }
            for ag in activity_graphs
        ]

        summaries.sort(
            key=lambda x: (
                str(x.get("activity_name", "")).lower(),
                int(x.get("activity_id", 0)),
            )
        )

        return {
            "database_file": str(self.qea_path),
            "package_path_filter": package_path,
            "include_subpackages": include_subpackages,
            "activity_count_total": len(summaries),
            "activity_count_returned": min(len(summaries), max_items),
            "activities": summaries[:max_items],
            "truncated": len(summaries) > max_items,
        }

    def get_activity_diagram_process_graph(
        self,
        activity_id: int,
        package_path: str = "",
        include_subpackages: bool = True,
        max_nodes: int = 500,
        max_edges: int = 1000,
    ) -> dict[str, Any]:
        max_nodes = max(1, min(int(max_nodes), 5000))
        max_edges = max(1, min(int(max_edges), 10000))

        activity_graphs = self.extract_operational_activity_graphs(
            package_path=package_path,
            include_subpackages=include_subpackages,
        )

        wanted = None
        for ag in activity_graphs:
            if int(ag.activity_id) == int(activity_id):
                wanted = ag
                break

        if wanted is None:
            raise ValueError(f"Activity id not found after extraction: {activity_id}")

        nodes = []
        for node_id, data in wanted.graph.nodes(data=True):
            node_entry = dict(data)
            node_entry["node_id"] = int(node_id)
            nodes.append(node_entry)

        edges = []
        for source_id, target_id, data in wanted.graph.edges(data=True):
            edge_entry = dict(data)
            edge_entry["source_id"] = int(source_id)
            edge_entry["target_id"] = int(target_id)
            edges.append(edge_entry)

        nodes.sort(key=lambda x: int(x.get("node_id", 0)))
        edges.sort(
            key=lambda x: (
                int(x.get("source_id", 0)),
                int(x.get("target_id", 0)),
            )
        )

        response = {
            "database_file": str(self.qea_path),
            "package_path_filter": package_path,
            "include_subpackages": include_subpackages,
            "activity": {
                "activity_id": wanted.activity_id,
                "activity_name": wanted.activity_name,
                "nodes_total": len(nodes),
                "edges_total": len(edges),
                "seed_count": wanted.seed_count,
                "diagram_id": (wanted.diagram or {}).get("diagram_id"),
                "diagram_name": (wanted.diagram or {}).get("name"),
                "extraction_warning": wanted.extraction_warning,
            },
            "nodes": nodes[:max_nodes],
            "edges": edges[:max_edges],
            "truncated_nodes": len(nodes) > max_nodes,
            "truncated_edges": len(edges) > max_edges,
            "max_nodes": max_nodes,
            "max_edges": max_edges,
        }

        return response
    
    # ── EXPORT ─────────────────────────────────────────────
    
    def export_element_report(self, element_name: str) -> dict:
        """Export a comprehensive report for a named element."""
        elements = self.find_elements(name=element_name, limit=10)
        if not elements:
            return {"error": f"No element found matching '{element_name}'"}
        
        reports = []
        for elem in elements[:3]:  # Max 3 to avoid overload
            detail = self.get_element_detail(elem['Object_ID'])
            reports.append(detail)
        
        return {
            "query": element_name,
            "matches_found": len(elements),
            "reports": reports
        }


# ═══════════════════════════════════════════════════════════════
# Open WebUI Tool Interface
# ═══════════════════════════════════════════════════════════════

class Tools:
    """
    EAM QEA Analyzer — Tools for Sparx Enterprise Architect Models.
    
    CRITICAL INSTRUCTION FOR THE LLM:
    When the user uploads a .qea or .qeax file, DO NOT rely on your internal document/RAG retrieval. 
    You MUST use the tools provided here to query the SQLite database structure directly.
    The qea_path parameter is OPTIONAL in all functions. If you omit it, the tool will automatically 
    discover and use the most recently uploaded .qea file from the user.
    
    Workflow for analyzing QEA models:
    1. Call `analyze_qea_statistics()` first to get an overview of element types and counts.
    2. Call `find_elements_in_qea(stereotype='...')` to find specific architecture elements (like 'Capability').
    3. Call `get_element_detail_from_qea(element_id=...)` to get full relationships and properties.
    4. For process analysis, call `list_process_packages_and_activities()` before extraction.
    5. Call `list_extracted_activity_graphs()` for compact extracted process summaries.
    6. Call `get_activity_diagram_process_graph(activity_id=...)` for one detailed process graph.
    """
    
    class Valves:
        """Configuration (not needed for basic operation)."""
        pass
    
    def __init__(self):
        self.valves = self.Valves()
    
    # ── PATH RESOLUTION ─────────────────────────────────────
    
    _QEA_SEARCH_DIRS = [
        "/app/backend/data/uploads",
        "/app/backend/data",
        "/mnt/data",
    ]
    
    @staticmethod
    def _discover_qea_files() -> list:
        """Auto-discover all .qea files in known upload directories."""
        files = []
        seen = set()
        for dir_path in Tools._QEA_SEARCH_DIRS:
            if not os.path.isdir(dir_path):
                continue
            try:
                for entry in os.scandir(dir_path):
                    if not entry.is_file():
                        continue
                    name = entry.name
                    if not (name.endswith('.qea') or name.endswith('.qeax')):
                        continue
                    path = entry.path
                    if path in seen:
                        continue
                    seen.add(path)
                    stat = entry.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    files.append({
                        "name": name,
                        "path": path,
                        "size_mb": round(size_mb, 2),
                    })
            except PermissionError:
                continue
        files.sort(key=lambda f: f["size_mb"], reverse=True)
        return files
    
    @staticmethod
    def _resolve_qea_path(qea_path: Optional[str] = None) -> str:
        """Resolve QEA file path, auto-discovering if needed."""
        if qea_path:
            try:
                resolved = QEAAnalyzer._resolve_path(qea_path)
                return str(resolved)
            except FileNotFoundError:
                pass
        
        files = Tools._discover_qea_files()
        if not files:
            raise FileNotFoundError(
                "No QEA files found in upload directories. "
                "Please upload a .qea file first."
            )
        return files[0]["path"]
    
    async def list_available_qea_files(self) -> str:
        """
        List all available QEA files in the upload directories.
        Use when the user asks what models are available.
        """
        try:
            files = self._discover_qea_files()
            if not files:
                return json.dumps({
                    "message": "No QEA files found. Please upload a .qea file.",
                    "files": []
                }, indent=2)
            return json.dumps({
                "message": f"Found {len(files)} QEA file(s)",
                "files": files
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    # ── ANALYSIS FUNCTIONS ──────────────────────────────────
    
    async def analyze_qea_statistics(self, qea_path: str = None) -> str:
        """
        Get comprehensive statistics about a QEA model.
        Shows element types, stereotypes, and counts.
        
        Args:
            qea_path: Absolute path to the .qea file
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            stats = analyzer.get_model_statistics()
            analyzer.close()
            return json.dumps(stats, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def find_elements_in_qea(
        self, qea_path: str = None, name: str = None, object_type: str = None,
        stereotype: str = None, package_id: int = None, limit: int = 50
    ) -> str:
        """
        Find elements in a QEA file by name, type, stereotype, or package.
        
        Args:
            qea_path: Absolute path to the .qea file
            name: Search in element name (partial match)
            object_type: Filter by Object_Type (e.g., 'Class', 'Component', 'Requirement')
            stereotype: Filter by Stereotype (e.g., 'Capability', 'OperationalActivity')
            package_id: Filter by Package_ID
            limit: Maximum results (default 50)
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            results = analyzer.find_elements(
                name=name, object_type=object_type,
                stereotype=stereotype, package_id=package_id, limit=limit
            )
            analyzer.close()
            return json.dumps(results, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_element_detail_from_qea(
        self, qea_path: str = None, element_id: int = None
    ) -> str:
        """
        Get complete detail for one element: attributes, operations,
        relationships, tagged values, implicit relationships, and diagrams.
        
        Args:
            qea_path: Path to the .qea file. If omitted, auto-discovers.
            element_id: The Object_ID of the element
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            detail = analyzer.get_element_detail(element_id)
            analyzer.close()
            return json.dumps(detail, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_relationships_from_qea(
        self, qea_path: str = None, element_id: int = None,
        connector_type: str = None, stereotype: str = None, limit: int = 100
    ) -> str:
        """
        Get relationships/connectors from a QEA file.
        
        Args:
            qea_path: Absolute path to the .qea file
            element_id: Get all relationships for this element (optional)
            connector_type: Filter by Connector_Type (e.g., 'Association', 'Composition')
            stereotype: Filter by Stereotype on the connector
            limit: Maximum results
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            results = analyzer.get_relationships(
                element_id=element_id, connector_type=connector_type,
                stereotype=stereotype, limit=limit
            )
            analyzer.close()
            return json.dumps(results, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def search_qea_elements(self, qea_path: str = None, query: str = "", limit: int = 50) -> str:
        """
        Full-text search across element names and notes in a QEA file.
        
        Args:
            qea_path: Absolute path to the .qea file
            query: Search term
            limit: Maximum results
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            results = analyzer.search_elements(query, limit)
            analyzer.close()
            return json.dumps(results, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_package_tree_from_qea(self, qea_path: str = None) -> str:
        """
        Get the complete package/folder hierarchy from a QEA file.
        
        Args:
            qea_path: Absolute path to the .qea file
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            tree = analyzer.get_package_tree()
            analyzer.close()
            return json.dumps(tree, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def find_elements_by_tagged_value(
        self, qea_path: str = None, tag_name: str = "", tag_value: str = None, limit: int = 100
    ) -> str:
        """
        Find elements by their tagged values. Essential for NAF architectures
        where metadata is stored as tagged values.
        
        Args:
            qea_path: Absolute path to the .qea file
            tag_name: Tagged value property name (e.g., 'OperationalActivity')
            tag_value: Optional filter on the value
            limit: Maximum results
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            results = analyzer.find_elements_by_tag(tag_name, tag_value, limit)
            analyzer.close()
            return json.dumps(results, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_qea_diagrams(self, qea_path: str = None) -> str:
        """
        List all diagrams in a QEA file with their element counts.
        
        Args:
            qea_path: Absolute path to the .qea file
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            diagrams = analyzer.get_diagrams()
            analyzer.close()
            return json.dumps(diagrams, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def list_process_packages_and_activities(
        self,
        qea_path: Optional[str] = None,
        package_path: str = "",
        include_subpackages: bool = True,
        include_empty_packages: bool = True,
    ) -> str:
        """
        Discover packages and Activity elements relevant to process extraction.

        Use this before calling extraction endpoints.
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            payload = analyzer.list_process_packages_and_activities(
                package_path=package_path,
                include_subpackages=include_subpackages,
                include_empty_packages=include_empty_packages,
            )
            analyzer.close()
            payload = _guard_process_response_size(payload, "list_process_packages_and_activities")
            return json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def list_extracted_activity_graphs(
        self,
        qea_path: str = None,
        package_path: str = "",
        include_subpackages: bool = True,
        max_items: int = 200,
    ) -> str:
        """
        Return compact summaries of diagram-extracted Activity process graphs.
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            payload = analyzer.summarize_extracted_activity_graphs(
                package_path=package_path,
                include_subpackages=include_subpackages,
                max_items=max_items,
            )
            analyzer.close()
            payload = _guard_process_response_size(payload, "list_extracted_activity_graphs")
            return json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def get_activity_diagram_process_graph(
        self,
        qea_path: str = None,
        activity_id: Optional[int] = None,
        package_path: str = "",
        include_subpackages: bool = True,
        max_nodes: int = 500,
        max_edges: int = 1000,
    ) -> str:
        """
        Return one detailed diagram-extracted Activity process graph.

        The payload is bounded via max_nodes and max_edges to avoid oversized outputs.
        """
        try:
            if activity_id is None:
                return json.dumps({"error": "activity_id is required"})
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            payload = analyzer.get_activity_diagram_process_graph(
                activity_id=activity_id,
                package_path=package_path,
                include_subpackages=include_subpackages,
                max_nodes=max_nodes,
                max_edges=max_edges,
            )
            analyzer.close()
            payload = _guard_process_response_size(payload, "get_activity_diagram_process_graph")
            return json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_naf_view_elements_from_qea(
        self, qea_path: str = None, view_type: str = "NAF-3"
    ) -> str:
        """
        Get elements belonging to a NAF view type (NAF-2 through NAF-7).
        
        Args:
            qea_path: Absolute path to the .qea file
            view_type: NAF view type (e.g., 'NAF-3', 'NAF-4', 'NAF-5')
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            results = analyzer.get_naf_view_elements(view_type)
            analyzer.close()
            return json.dumps(results, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def execute_qea_sql(
        self, qea_path: str = None, sql: str = "", limit: int = 100
    ) -> str:
        """
        Execute a read-only SQL query against a QEA file.
        Use this for advanced analysis that the higher-level functions don't cover.
        Only SELECT queries are allowed.
        
        Args:
            qea_path: Absolute path to the .qea file
            sql: SELECT query to execute
            limit: Maximum rows to return
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            results = analyzer.execute_query(sql, limit)
            analyzer.close()
            return json.dumps(results, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_qea_table_schema(self, qea_path: str = None, table_name: str = None) -> str:
        """
        Get the column schema for tables in a QEA file.
        If no table specified, returns all table names.
        
        Args:
            qea_path: Absolute path to the .qea file
            table_name: Specific table name (optional, e.g., 't_object')
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            if table_name:
                schema = analyzer.get_table_schema(table_name)
            else:
                schema = analyzer.list_tables()
            analyzer.close()
            return json.dumps(schema, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def export_qea_element_report(
        self, qea_path: Optional[str] = None, element_name: str = ""
    ) -> str:
        """
        Export a comprehensive report for a named element — includes
        all details, relationships, tagged values, and diagrams.
        
        Args:
            qea_path: Absolute path to the .qea file
            element_name: Name of the element to report on
        """
        try:
            path = self._resolve_qea_path(qea_path)
            analyzer = QEAAnalyzer(path)
            report = analyzer.export_element_report(element_name)
            analyzer.close()
            return json.dumps(report, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════
# Standalone CLI (for testing outside Open WebUI)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python eam_qea_tool.py <qea_file> [command]")
        print("\nCommands:")
        print("  stats        - Model statistics")
        print("  packages     - Package tree")
        print("  types        - Object types")
        print("  search <q>   - Search elements")
        print("  detail <id>  - Element detail by Object_ID")
        print("  tags <name>  - Find elements by tagged value")
        sys.exit(1)
    
    qea_path = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else "stats"
    
    analyzer = QEAAnalyzer(qea_path)
    
    if cmd == "stats":
        result = analyzer.get_model_statistics()
    elif cmd == "packages":
        result = analyzer.get_package_tree()
    elif cmd == "types":
        result = analyzer.list_object_types()
    elif cmd == "search":
        query = sys.argv[3] if len(sys.argv) > 3 else ""
        result = analyzer.search_elements(query)
    elif cmd == "detail":
        eid = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        result = analyzer.get_element_detail(eid)
    elif cmd == "tags":
        tag = sys.argv[3] if len(sys.argv) > 3 else ""
        result = analyzer.find_elements_by_tag(tag)
    else:
        result = {"error": f"Unknown command: {cmd}"}
    
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    analyzer.close()