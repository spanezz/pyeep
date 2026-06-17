from collections.abc import Generator, Iterable

#: Routing key identifying a connected component
#: It encodes component names in the path from the hub down to the components
type RoutingKey = str

#: Multiple destination routing keys
type RoutingKeys = tuple[str, ...]


def build_routing_keys(rks: Iterable[RoutingKey]) -> RoutingKeys:
    """Compress a list of routing keys into a RoutingKeys."""
    return tuple(rks)


def expand_routing_keys(rks: RoutingKeys) -> Generator[RoutingKey]:
    """Generate all nodes visited by a RoutingKeys."""
    yield from rks
