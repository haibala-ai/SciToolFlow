"""Academic descriptive figure; no baseline performance or speedup claims."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
BASE=Path(__file__).resolve().parents[1];m=json.loads((BASE/'metadata.json').read_text())
strata=json.loads((BASE/'strata.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':'scimas-special-100-v2'})
fig,axes=plt.subplots(1,3,figsize=(12.3,3.6),gridspec_kw={'width_ratios':[1.25,1,1.1]})
colors={'advanced':'#304E71','intermediate':'#5E9694','foundation':'#C4BAA2'}
domains=['Chemical','Material','Biology','MachineLearning'];labels=['Chemistry','Materials','Bio / ecology','Numerical / ML']
left=[0]*4
for tier in ['advanced','intermediate','foundation']:
 counts=[sum(t['domain']==d and t['difficulty_tier']==tier for t in strata['tasks']) for d in domains]
 axes[0].barh(labels,counts,left=left,height=.6,color=colors[tier],label=tier.capitalize())
 for i,(start,n) in enumerate(zip(left,counts)):axes[0].text(start+n/2,i,str(n),ha='center',va='center',color='white' if tier!='foundation' else '#24333D',fontsize=9)
 left=[a+b for a,b in zip(left,counts)]
axes[0].invert_yaxis();axes[0].set(xlabel='Studies',title='A   Scientific scope and design tiers',xlim=(0,27));axes[0].legend(loc='upper center',bbox_to_anchor=(.5,-.18),ncol=3,frameon=False,fontsize=8,columnspacing=.8)
calls=[t['reference_scientific_calls'] for t in m['tasks']]
axes[1].hist(calls,bins=[i-.5 for i in range(min(calls),max(calls)+2)],color='#304E71',edgecolor='white',linewidth=1.1)
axes[1].set(xlabel='Scientific calls per reference',ylabel='Studies',title='B   Actual reference workload')
widths=[t['source_reviewed_applicable_ready_width'] for t in m['tasks']]
axes[2].hist(widths,bins=[i-.5 for i in range(min(widths),max(widths)+2)],color='#5E9694',edgecolor='white',linewidth=1.1)
axes[2].set(xlabel='Distinct reviewed ready observations',ylabel='Studies',title='C   Source-reviewed branch readiness')
for ax in axes:
 ax.xaxis.set_major_locator(MaxNLocator(integer=True));ax.yaxis.set_major_locator(MaxNLocator(integer=True)) if ax is not axes[0] else None
 ax.set_axisbelow(True);ax.grid(axis='x' if ax is axes[0] else 'y',color='#DDE3E8',alpha=.7,linewidth=.7)
fig.tight_layout(rect=(0,.11,1,1),w_pad=2)
fig.text(.5,.02,'Special-100 v1  |  Design-based tiers; readiness excludes inactive branches and reused observations. No measured speedup.',ha='center',fontsize=9,color='#586470')
fig.savefig(BASE/'overview.svg',bbox_inches='tight',metadata={'Date':None});plt.close(fig)
