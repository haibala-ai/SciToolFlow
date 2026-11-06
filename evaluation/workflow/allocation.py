"""Order-independent bounded credit assignment for task-scoped certificates."""

from collections import deque


def allocate_certificates(candidates, capacities, quotas):
    """Maximize useful-work credit, then valid exemptions, without greedy order bias.

    Candidates contain (execution signature, category, rule ID, observation ID).
    One execution can obtain at most one credit. A rule and its category both
    have finite capacities. No scientific predicate is evaluated or relaxed here.
    """
    candidates = sorted(set(candidates))
    if not candidates:
        return []
    executions = sorted({item[0] for item in candidates})
    rules = sorted({(item[1], item[2]) for item in candidates})
    labels = ["source", "sink"] + [("execution", s) for s in executions]
    labels += [("rule", *key) for key in rules]
    labels += [("category", c) for c in sorted(quotas)]
    ids = {label: i for i, label in enumerate(labels)}
    graph = [[] for _ in labels]

    def edge(a, b, capacity, cost):
        forward = [b, len(graph[b]), capacity, cost]
        reverse = [a, len(graph[a]), 0, -cost]
        graph[a].append(forward)
        graph[b].append(reverse)
        return forward

    source, sink = ids["source"], ids["sink"]
    for signature in executions:
        edge(source, ids[("execution", signature)], 1, 0)
    for category, rule in rules:
        edge(ids[("rule", category, rule)], ids[("category", category)],
             capacities[(category, rule)], 0)
    for category, quota in quotas.items():
        edge(ids[("category", category)], sink, quota, 0)
    recorded, seen = [], set()
    for signature, category, rule, observation in candidates:
        key = (signature, category, rule)
        if key in seen:
            continue
        seen.add(key)
        benefit = len(executions) + 1 if category == "useful_work_rules" else 1
        link = edge(ids[("execution", signature)], ids[("rule", category, rule)], 1, -benefit)
        recorded.append((link, (signature, category, rule, observation)))

    while True:
        distance, previous = [float("inf")] * len(labels), [None] * len(labels)
        distance[source] = 0
        queue, queued = deque([source]), {source}
        while queue:
            node = queue.popleft()
            queued.remove(node)
            for i, (target, _, capacity, cost) in enumerate(graph[node]):
                if capacity and distance[node] + cost < distance[target]:
                    distance[target] = distance[node] + cost
                    previous[target] = (node, i)
                    if target not in queued:
                        queue.append(target)
                        queued.add(target)
        if previous[sink] is None or distance[sink] >= 0:
            break
        node = sink
        while node != source:
            parent, index = previous[node]
            link = graph[parent][index]
            link[2] -= 1
            graph[node][link[1]][2] += 1
            node = parent
    return [item for link, item in recorded if link[2] == 0]
