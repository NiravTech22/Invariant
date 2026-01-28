import unittest
from unittest.mock import MagicMock, patch
import sys
import types

# Mock rclpy before importing invariant
mock_rclpy = MagicMock()
mock_rclpy.ok.return_value = True
mock_rclpy.create_node.return_value = MagicMock()

# Setup mocks for nodes and introspection
mock_node = mock_rclpy.create_node.return_value
mock_node.get_node_names_and_namespaces.return_value = [
    ("node_a", "/ns"),
    ("node_b", "/ns"),
]
# node_a publishes topic_x
mock_node.get_publisher_names_and_types_by_node.side_effect = lambda name, ns: [("topic_x", ["std_msgs/msg/String"])] if name == "node_a" else []
# node_b subscribes to topic_x
mock_node.get_subscriber_names_and_types_by_node.side_effect = lambda name, ns: [("topic_x", ["std_msgs/msg/String"])] if name == "node_b" else []

# Inject into sys.modules
sys.modules["rclpy"] = mock_rclpy
sys.modules["rclpy.node"] = MagicMock()

# Now import invariant modules
from invariant.ros.bridge import ActiveBridge
from invariant.execution.ros_runner import ROSEngine
from invariant.core.config import ExperimentConfig

class TestROSIntegration(unittest.TestCase):
    def test_bridge_introspection(self):
        bridge = ActiveBridge()
        self.assertTrue(bridge.active)
        
        graph = bridge.introspect_graph()
        self.assertEqual(len(graph.node_ids), 2)
        
        # Verify edge
        # Expected: /ns/node_a -> /ns/node_b
        node_a_id = "/ns/node_a"
        node_b_id = "/ns/node_b"
        
        self.assertTrue(graph.graph.has_edge(node_a_id, node_b_id))
        
    def test_ros_runner(self):
        bridge = ActiveBridge()
        config = ExperimentConfig({"run_id": "test_run"})
        runner = ROSEngine(bridge, config)
        
        trace = runner.monitor(duration_sec=0.1)
        self.assertIsNotNone(trace)
        self.assertEqual(trace.run_id, "test_run")
        
        # Verify spin was called
        # We can't easily check spin count without more mocking, but we verified it ran
        
if __name__ == '__main__':
    unittest.main()
