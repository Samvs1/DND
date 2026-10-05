"""The region graph: nodes and directed, optionally locked travel edges (SPEC 9, M5.2).

Built by code from a `RegionPlan` (`aidm.rules.world_graph.build_region_graph`); the AI never
draws a map. Plain frozen data.

Public API:
- `GraphEdge(src, dst, requires_visited, requires_resolved)`: you may travel `src -> dst` once
  every node in `requires_visited` was visited and every region id in `requires_resolved` is
  resolved.
- `RegionGraph(region_id, tier, arrival, spokes, gateway, nodes, edges, boss_id, boss_lair)`.
- `CampaignGraph(regions, links)`: one graph per act plus the inter-act links (the gateway of act
  N leads to the arrival of act N+1 once region N is resolved); `all_edges()`.
"""

from pydantic import BaseModel, ConfigDict, Field


class _Graph(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GraphEdge(_Graph):
    src: str
    dst: str
    requires_visited: tuple[str, ...] = ()
    requires_resolved: tuple[str, ...] = ()


class RegionGraph(_Graph):
    region_id: str
    tier: int = Field(ge=1, le=3)
    arrival: str
    spokes: tuple[str, ...]
    gateway: str
    nodes: tuple[str, ...]
    edges: tuple[GraphEdge, ...]
    boss_id: str
    boss_lair: str


class CampaignGraph(_Graph):
    regions: tuple[RegionGraph, ...]
    links: tuple[GraphEdge, ...] = ()

    def all_edges(self) -> tuple[GraphEdge, ...]:
        return tuple(e for r in self.regions for e in r.edges) + self.links
