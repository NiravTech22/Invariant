import time
from typing import List, Dict, Any, Optional
try:
    import rclpy
    from rclpy.node import Node as RosNode
except ImportError:
    rclpy = None
    RosNode = object

from ..workflow.graph import WorkflowGraph
from ..workflow.node import Node, Port, PortType

class ActiveBridge:
    """Active ROS 2 introspection bridge."""
    
    def __init__(self, node_name: str = "invariant_introspector"):
        self.active = False
        if rclpy:
            if not rclpy.ok():
                rclpy.init()
            self.node = rclpy.create_node(node_name)
            self.active = True
        else:
            print("Warning: rclpy not found. ROS 2 features will be unavailable.")
            self.node = None

    def introspect_graph(self) -> WorkflowGraph:
        """Captures a snapshot of the running ROS 2 system as a WorkflowGraph."""
        if not self.active:
            return WorkflowGraph()

        graph = WorkflowGraph()
        
        # Get all nodes
        node_names_dims = self.node.get_node_names_and_namespaces()
        
        for name, namespace in node_names_dims:
            full_name = f"{namespace}/{name}".replace("//", "/")
            
            # Introspect pubs/subs
            # Note: This API returns list of (topic_name, [types])
            pubs = self.node.get_publisher_names_and_types_by_node(name, namespace)
            subs = self.node.get_subscriber_names_and_types_by_node(name, namespace)
            
            ports = []
            
            for topic, types in subs:
                ports.append(Port(
                    name=topic,
                    port_type=PortType.INPUT,
                    data_type=types[0] if types else "unknown"
                ))
                
            for topic, types in pubs:
                ports.append(Port(
                    name=topic,
                    port_type=PortType.OUTPUT,
                    data_type=types[0] if types else "unknown"
                ))
            
            # Create Node
            node = Node(
                id=full_name,
                node_type="ros_node",
                ports=ports
            )
            graph.add_node(node)

        # Infer edges based on topic matching
        # This is a heuristic: if A pub T and B sub T, A->B
        node_ids = graph.node_ids
        for source_id in node_ids:
            source_node = graph.get_node(source_id)
            for out_port in source_node.output_ports:
                topic = out_port.name
                
                # Find targets
                for target_id in node_ids:
                    if source_id == target_id:
                        continue
                        
                    target_node = graph.get_node(target_id)
                    for in_port in target_node.input_ports:
                        if in_port.name == topic:
                            # Found a connection
                            try:
                                graph.add_edge(
                                    source_id=source_id,
                                    target_id=target_id,
                                    source_port=out_port.name,
                                    target_port=in_port.name
                                )
                            except ValueError:
                                pass # Ignore cycles or duplicate edges for now

        return graph

    def spin_once(self, timeout_sec=0.1):
        if self.active:
            rclpy.spin_once(self.node, timeout_sec=timeout_sec)

    def shutdown(self):
        if self.active:
            self.node.destroy_node()
            rclpy.shutdown()
            self.active = False

