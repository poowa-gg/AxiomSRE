import pytest
from backend.api.schemas import CausalGraph, CausalNode, CausalEdge, NodeType
from backend.services.causal_engine import CausalInferenceEngine

def test_valid_dag_analysis():
    nodes = [
        CausalNode(id="A", label="External Cloud Drop", type=NodeType.EXTERNAL_FACTOR, confidence=0.99, service_or_entity="Cloudflare", evidence_snippet=""),
        CausalNode(id="B", label="Missing Circuit Breaker", type=NodeType.ROOT_CAUSE, confidence=0.95, service_or_entity="Webhook", evidence_snippet=""),
        CausalNode(id="C", label="Thread Pool Exhaustion", type=NodeType.INTERMEDIATE_CASCADE, confidence=0.90, service_or_entity="Webhook", evidence_snippet=""),
        CausalNode(id="D", label="504 Timeouts Spike", type=NodeType.SURFACE_SYMPTOM, confidence=1.00, service_or_entity="Gateway", evidence_snippet="")
    ]
    edges = [
        CausalEdge(source="A", target="B", relationship="EXPOSES", confidence=0.98),
        CausalEdge(source="B", target="C", relationship="AMPLIFIES", confidence=0.95),
        CausalEdge(source="C", target="D", relationship="TRIGGERS", confidence=0.99)
    ]
    graph = CausalGraph(
        nodes=nodes,
        edges=edges,
        root_cause_node_id="B",
        root_cause_explanation="Absence of circuit breaker",
        mathematical_confidence=0.97,
        counterfactual_proof="Removing node B severs the chain"
    )

    analysis = CausalInferenceEngine.validate_and_analyze_dag(graph)
    assert analysis["is_valid_dag"] is True
    assert analysis["root_cause_node"] == "B"
    assert len(analysis["topological_order"]) == 4
    assert analysis["path_confidence"] > 0.85

def test_cyclic_graph_detection():
    # Intentionally create cycle A -> B -> C -> A
    nodes = [
        CausalNode(id="A", label="Node A", type=NodeType.ROOT_CAUSE, confidence=0.9, service_or_entity="S1", evidence_snippet=""),
        CausalNode(id="B", label="Node B", type=NodeType.INTERMEDIATE_CASCADE, confidence=0.9, service_or_entity="S2", evidence_snippet=""),
        CausalNode(id="C", label="Node C", type=NodeType.SURFACE_SYMPTOM, confidence=0.9, service_or_entity="S3", evidence_snippet="")
    ]
    edges = [
        CausalEdge(source="A", target="B", relationship="CAUSES", confidence=0.9),
        CausalEdge(source="B", target="C", relationship="CAUSES", confidence=0.9),
        CausalEdge(source="C", target="A", relationship="CAUSES_CYCLE", confidence=0.9)
    ]
    graph = CausalGraph(
        nodes=nodes,
        edges=edges,
        root_cause_node_id="A",
        root_cause_explanation="Cyclic error",
        mathematical_confidence=0.5,
        counterfactual_proof="None"
    )

    analysis = CausalInferenceEngine.validate_and_analyze_dag(graph)
    assert analysis["is_valid_dag"] is False
    assert "cyclic" in analysis["error"]
