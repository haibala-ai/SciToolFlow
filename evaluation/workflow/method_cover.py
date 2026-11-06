"""Bounded exact selection of scientific method witnesses shared across goals.

One batch observation can cover several capabilities. Choosing each capability
independently can otherwise count a redundant complete parallel method as useful.
Masks identify distinct actual executions, not reference steps or model plans.
"""
from fractions import Fraction


def select_methods(groups, base=0, limit=100000):
    """Choose minimum-union execution masks; unresolved searches stay explicit.

``groups`` maps a stable capability ID to (route-node tuple, execution mask)
options. All options have already passed scientific predicates. No new evidence
is inferred here. Disjoint choice components are optimized independently.
"""
    if type(limit)is not int or limit<0:raise ValueError('Method search limit must be nonnegative')
    if not groups:return {},False,0
    forced=base
    for options in groups.values():
        if not options:raise ValueError('Method groups require an evidenced option')
        common=options[0][1]
        for _,mask in options[1:]:common&=mask
        forced|=common
    prepared={}
    for name,options in sorted(groups.items()):
        unique={}
        for route,mask in sorted(options,key=lambda x:tuple(x[0])):
            unique.setdefault(mask&~forced,(tuple(route),mask&~forced))
        masks=sorted(unique,key=lambda m:(m.bit_count(),m))
        kept=[]
        for mask in masks:
            if not any(other&mask==other for other in kept):kept.append(mask)
        prepared[name]=[unique[mask]for mask in kept]
    potential={name:0 for name in prepared}
    for name,options in prepared.items():
        for _,mask in options:potential[name]|=mask
    remaining=set(prepared);components=[]
    while remaining:
        seed=min(remaining);remaining.remove(seed);component={seed};pending=[seed]
        while pending:
            name=pending.pop()
            linked={other for other in remaining if potential[name]&potential[other]}
            remaining-=linked;component|=linked;pending.extend(sorted(linked))
        components.append(sorted(component))
    selected={};visits=0;truncated=False
    for component in components:
        def completed(names,mask):
            return {name:min((route for route,value in prepared[name]if value&~mask==0),default=None)
                    for name in names}
        def priority(option,names,mask):
            route,value=option;after=mask|value
            covered=sum(any(other&~after==0 for _,other in prepared[name])for name in names)
            extra=(value&~mask).bit_count()
            return Fraction(extra,max(1,covered)),extra,route
        # Deterministic valid upper bound; exact search proves or improves it.
        pending=set(component);mask=0;picks={}
        while pending:
            ready=completed(pending,mask)
            ready={name:route for name,route in ready.items()if route is not None}
            if ready:picks.update(ready);pending-=ready.keys();continue
            option=min((option for name in sorted(pending)for option in prepared[name]),
                       key=lambda option:priority(option,pending,mask))
            mask|=option[1]
        best_count=mask.bit_count();best=dict(picks)

        def walk(names,mask,picks):
            nonlocal visits,truncated,best,best_count
            ready=completed(names,mask)
            ready={name:route for name,route in ready.items()if route is not None}
            names=tuple(name for name in names if name not in ready)
            picks={**picks,**ready}
            count=mask.bit_count()
            if not names:
                if count<best_count:best_count=count;best=dict(picks)
                return
            lower=count+max(min((value&~mask).bit_count()for _,value in prepared[name])for name in names)
            if lower>=best_count:return
            if visits>=limit:truncated=True;return
            visits+=1
            name=min(names,key=lambda n:(len(prepared[n]),n))
            rest=tuple(n for n in names if n!=name)
            for route,value in sorted(prepared[name],key=lambda option:priority(option,names,mask)):
                if (mask|value).bit_count()>=best_count:continue
                walk(rest,mask|value,{**picks,name:route})
                if truncated:return
        walk(tuple(component),0,{})
        selected.update(best)
    return selected,truncated,visits
