"""
Sector graph and pathfinding using Dijkstra's algorithm.
Creates navigation graph between nodes and computes optimal routes.
"""

import heapq
import logging
from typing import List, Tuple, Dict, Optional, Set
from agent.nav.node_placement import NavigationNode

logger = logging.getLogger(__name__)


class NodeEdge:
    """Edge between two navigation nodes."""
    
    def __init__(self, from_node: NavigationNode, to_node: NavigationNode, 
                 distance: float, same_sector: bool = False):
        self.from_node = from_node
        self.to_node = to_node
        self.distance = distance
        self.same_sector = same_sector
    
    def __repr__(self):
        sector_info = "same sector" if self.same_sector else "cross-sector"
        return f"Edge({self.from_node.node_id}->{self.to_node.node_id}, {self.distance:.1f}, {sector_info})"


class PathNode:
    """Node for Dijkstra's algorithm."""
    
    def __init__(self, nav_node: NavigationNode, cost: float = float('inf'), parent: Optional['PathNode'] = None):
        self.nav_node = nav_node
        self.cost = cost
        self.parent = parent
    
    def __lt__(self, other):
        """For priority queue ordering."""
        return self.cost < other.cost
    
    def __eq__(self, other):
        return self.nav_node.node_id == other.nav_node.node_id


class SectorGraph:
    """Graph of navigation nodes with pathfinding."""
    
    def __init__(self):
        self.nodes: Dict[int, NavigationNode] = {}
        self.edges: Dict[int, List[NodeEdge]] = {}  # node_id -> list of edges
        self.sector_nodes: Dict[int, Set[int]] = {}  # sector_id -> set of node_ids
    
    def build_from_placement(self, node_placement, sectors, 
                            max_cross_sector_distance: float = 500.0) -> bool:
        """
        Build graph from placed nodes.
        
        Creates edges between:
        - Nodes within same sector (all pairs)
        - Adjacent sectors (nearest nodes)
        
        Args:
            node_placement: NodePlacement instance with placed nodes
            sectors: Dictionary of sector_id -> SectorPolygon
            max_cross_sector_distance: Max distance for cross-sector edges
        
        Returns:
            True if graph built successfully
        """
        self.nodes = node_placement.nodes.copy()
        self.edges = {node_id: [] for node_id in self.nodes.keys()}
        self.sector_nodes = {}
        
        # Organize nodes by sector
        for node_id, node in self.nodes.items():
            sector_id = node.sector_id
            if sector_id not in self.sector_nodes:
                self.sector_nodes[sector_id] = set()
            self.sector_nodes[sector_id].add(node_id)
        
        # Create edges within sectors
        for sector_id, node_ids in self.sector_nodes.items():
            node_list = [self.nodes[nid] for nid in node_ids]
            
            # Create edges between all node pairs in sector
            for i in range(len(node_list)):
                for j in range(i + 1, len(node_list)):
                    n1 = node_list[i]
                    n2 = node_list[j]
                    distance = n1.distance_to(n2.x, n2.y)
                    
                    edge1 = NodeEdge(n1, n2, distance, same_sector=True)
                    edge2 = NodeEdge(n2, n1, distance, same_sector=True)
                    
                    self.edges[n1.node_id].append(edge1)
                    self.edges[n2.node_id].append(edge2)
        
        # Create edges between adjacent sectors
        for sector_id, polygon in sectors.items():
            adjacent_sectors = sectors[sector_id].get_adjacent_sectors() if hasattr(sectors[sector_id], 'get_adjacent_sectors') else set()
            
            # Get this sector's nodes
            this_sector_nodes = [self.nodes[nid] for nid in self.sector_nodes.get(sector_id, [])]
            
            for adj_sector_id in adjacent_sectors:
                if adj_sector_id not in self.sector_nodes:
                    continue
                
                # Get adjacent sector's nodes
                adj_nodes = [self.nodes[nid] for nid in self.sector_nodes[adj_sector_id]]
                
                # Connect nearest nodes between sectors
                if this_sector_nodes and adj_nodes:
                    # Find shortest distance
                    min_distance = float('inf')
                    best_pair = None
                    
                    for n1 in this_sector_nodes:
                        for n2 in adj_nodes:
                            distance = n1.distance_to(n2.x, n2.y)
                            if distance < min_distance:
                                min_distance = distance
                                best_pair = (n1, n2)
                    
                    # Add edge if within distance threshold
                    if best_pair and min_distance <= max_cross_sector_distance:
                        n1, n2 = best_pair
                        
                        edge1 = NodeEdge(n1, n2, min_distance, same_sector=False)
                        edge2 = NodeEdge(n2, n1, min_distance, same_sector=False)
                        
                        self.edges[n1.node_id].append(edge1)
                        self.edges[n2.node_id].append(edge2)
        
        logger.info(f"Built graph with {len(self.nodes)} nodes")
        total_edges = sum(len(edges) for edges in self.edges.values())
        logger.info(f"Total edges: {total_edges} (directed)")
        
        return len(self.nodes) > 0
    
    def dijkstra(self, start_node: NavigationNode, goal_node: NavigationNode) -> Optional[List[NavigationNode]]:
        """
        Find shortest path between two nodes using Dijkstra's algorithm.
        
        Args:
            start_node: Starting navigation node
            goal_node: Goal navigation node
        
        Returns:
            List of NavigationNode objects forming the path, or None if no path exists
        """
        if start_node.node_id not in self.nodes or goal_node.node_id not in self.nodes:
            logger.warning("Start or goal node not in graph")
            return None
        
        # Initialize
        distances = {node_id: float('inf') for node_id in self.nodes.keys()}
        distances[start_node.node_id] = 0
        parents = {node_id: None for node_id in self.nodes.keys()}
        
        pq = [PathNode(start_node, 0)]
        visited = set()
        
        while pq:
            current_path_node = heapq.heappop(pq)
            current_node = current_path_node.nav_node
            
            if current_node.node_id in visited:
                continue
            
            visited.add(current_node.node_id)
            
            # Found goal
            if current_node.node_id == goal_node.node_id:
                # Reconstruct path
                path = []
                node_id = goal_node.node_id
                while node_id is not None:
                    path.append(self.nodes[node_id])
                    node_id = parents[node_id]
                
                path.reverse()
                logger.debug(f"Path found: {len(path)} nodes, total distance: {distances[goal_node.node_id]:.1f}")
                return path
            
            # Explore neighbors
            for edge in self.edges[current_node.node_id]:
                neighbor_id = edge.to_node.node_id
                
                if neighbor_id in visited:
                    continue
                
                new_distance = distances[current_node.node_id] + edge.distance
                
                if new_distance < distances[neighbor_id]:
                    distances[neighbor_id] = new_distance
                    parents[neighbor_id] = current_node.node_id
                    
                    heapq.heappush(pq, PathNode(edge.to_node, new_distance))
        
        logger.warning(f"No path found from node {start_node.node_id} to {goal_node.node_id}")
        return None
    
    def find_route_to_unvisited(self, current_node: NavigationNode,
                               unvisited_nodes: List[NavigationNode]) -> Optional[List[NavigationNode]]:
        """
        Find route from current node to nearest unvisited node.
        
        Args:
            current_node: Current position node
            unvisited_nodes: List of unvisited navigation nodes
        
        Returns:
            Path to nearest unvisited node, or None if none reachable
        """
        if not unvisited_nodes:
            return None
        
        # Find nearest unvisited node
        best_distance = float('inf')
        nearest_node = None
        
        for node in unvisited_nodes:
            distance = current_node.distance_to(node.x, node.y)
            if distance < best_distance:
                best_distance = distance
                nearest_node = node
        
        if nearest_node is None:
            return None
        
        # Find path to nearest unvisited node
        return self.dijkstra(current_node, nearest_node)
    
    def find_exploration_route(self, current_node: NavigationNode,
                              unvisited_sectors: Set[int],
                              sector_nodes: Dict[int, Set[int]]) -> Optional[List[NavigationNode]]:
        """
        Find route from current node through unvisited sectors.
        Uses greedy approach: visit nearest unvisited sector first.
        
        Args:
            current_node: Current position node
            unvisited_sectors: Set of sector IDs not yet visited
            sector_nodes: Mapping of sector_id -> set of node_ids
        
        Returns:
            Path to start exploring unvisited sectors, or None
        """
        if not unvisited_sectors:
            return None
        
        # Find nearest node in an unvisited sector
        best_distance = float('inf')
        target_node = None
        
        for sector_id in unvisited_sectors:
            node_ids = sector_nodes.get(sector_id, set())
            
            for node_id in node_ids:
                node = self.nodes[node_id]
                distance = current_node.distance_to(node.x, node.y)
                
                if distance < best_distance:
                    best_distance = distance
                    target_node = node
        
        if target_node is None:
            return None
        
        return self.dijkstra(current_node, target_node)
    
    def get_connected_component(self, node_id: int) -> Set[int]:
        """Get all nodes reachable from given node."""
        visited = set()
        queue = [node_id]
        
        while queue:
            current_id = queue.pop(0)
            
            if current_id in visited:
                continue
            
            visited.add(current_id)
            
            for edge in self.edges.get(current_id, []):
                if edge.to_node.node_id not in visited:
                    queue.append(edge.to_node.node_id)
        
        return visited
    
    def get_graph_stats(self) -> Dict:
        """Get statistics about the graph."""
        total_nodes = len(self.nodes)
        total_edges = sum(len(edges) for edges in self.edges.values())
        
        within_sector_edges = sum(
            sum(1 for e in edges if e.same_sector)
            for edges in self.edges.values()
        )
        
        cross_sector_edges = total_edges - within_sector_edges
        
        return {
            'total_nodes': total_nodes,
            'total_edges': total_edges,
            'within_sector_edges': within_sector_edges,
            'cross_sector_edges': cross_sector_edges,
            'avg_edges_per_node': total_edges / total_nodes if total_nodes > 0 else 0
        }
