"""Individually designed synthetic material studies; no reference answers or trajectories.

All structures are pedagogical, generated explicitly here, and are not measured
structures. No numerical answer is baked into an evaluator.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def lit(v): return {"value": v}
def obs(n, p): return {"source": "node", "node": n, "path": p}
def op(name, *args, **kw): return {"operation": name, "args": list(args), **kw}
def arr(*args): return op("array", *args)


def cif(cell, sites):
    a,b,c,alpha,beta,gamma = cell
    lines = ["data_controlled_synthetic", "_symmetry_space_group_name_H-M 'P 1'", "_symmetry_Int_Tables_number 1",
             f"_cell_length_a {a}",f"_cell_length_b {b}",f"_cell_length_c {c}",
             f"_cell_angle_alpha {alpha}",f"_cell_angle_beta {beta}",f"_cell_angle_gamma {gamma}",
             "loop_", "_symmetry_equiv_pos_as_xyz", "'x,y,z'", "loop_",
             "_atom_site_label", "_atom_site_type_symbol", "_atom_site_fract_x", "_atom_site_fract_y", "_atom_site_fract_z", "_atom_site_occupancy"]
    for i, site in enumerate(sites):
        el,x,y,z,*occupancy=site
        lines.append(f"{el}{i+1} {el} {x} {y} {z} {occupancy[0] if occupancy else 1}")
    return "\n".join(lines)+"\n"


def poscar(cell, species, counts, coords):
    return "Synthetic fixed identities\n1.0\n"+"\n".join(" ".join(map(str,r)) for r in cell)+"\n"+" ".join(species)+"\n"+" ".join(map(str,counts))+"\nDirect\n"+"\n".join(" ".join(map(str,r)) for r in coords)+"\n"


class Study:
    def __init__(self, number, ids, goal, showcase=False):
        self.id=f"SMAS-{number:04d}"
        self.inputs={"sample_ids":ids,"provenance":"Explicit synthetic geometries for a controlled computational study; not experimental measurements."}
        self.assets={};self.nodes=[];self.outcomes=[];self.props={};self.conditions={}
        self.goal=goal;self.showcase=showcase;self.repair="None required for the valid geometry panel."
        self.early="All stated scientific comparisons require their evidence; omit unrelated property calculations."
        self.branches=[]
    def file(self,label,text,ext="cif"):
        name=f"{self.id}_{label}.{ext}"
        self.assets[name]=text
        self.inputs.setdefault("structures",{})[label]="asset://"+name
        return name
    def measure(self,n,tool,args,sources,port,typ="number"):
        rules=[]
        for arg,name,hashport in sources:
            aliases=[name,"asset://"+name,"tasks/full/assets/"+name,str(ROOT/"tasks/assets"/name),str(ROOT/"evaluation/authoring/special100/assets"/name),"evaluation/authoring/special100/assets/"+name]
            rules.append({"path":"/"+arg,"op":"one_of","value":aliases})
        for k,v in args.items():
            if k not in [s[0] for s in sources]: rules.append({"path":"/"+k,"op":"eq","value":v})
        out=[{"path":port,"op":"type","value":typ}]
        for arg,name,hp in sources: out.append({"path":hp,"op":"eq","value":hashlib.sha256(self.assets[name].encode()).hexdigest()})
        self.nodes.append({"id":n,"alternatives":[{"tools":[tool],"input_rules":rules,"output_rules":out}]})
        return obs(n,port)
    def source(self,n,tool,file,arg,port,typ="number",**kw):
        return self.measure(n,tool,{arg:file,**kw},[(arg,file,"/source_sha256")],port,typ)
    def density(self,label,file): return self.source("density_"+label,"CalculateDensity",file,"file_name","/density_g_per_cm3")
    def symmetry(self,label,file,tol=.01):
        return self.source("symmetry_"+label,"CalculateSymmetry",file,"file_name","/international_number","integer",symprec=tol,angle_tolerance=1.0)
    def neighbors(self,label,file,radius):
        return self.source("neighbors_"+label,"PeriodicNeighborList",file,"structure_file","/edge_count","integer",cutoff_angstrom=radius)
    def powder(self,label,file,wavelength=1.5406):
        return self.source("powder_"+label,"PowderDiffractionPattern",file,"structure_file","/peaks/0/two_theta_deg",wavelength_angstrom=wavelength,two_theta_min_deg=5.0,two_theta_max_deg=100.0)
    def composition(self,label,file):
        return self.source("composition_"+label,"GetElementComposition",file,"file_name","/element_amounts","object")
    def read(self,label,file): return self.source("read_"+label,"ReadCrystalStructure",file,"structure_file","/structure/sites","array")
    def match(self,label,a,b,scale=False,primitive=True):
        return self.measure("match_"+label,"CrystalStructureMatch",dict(structure_a=a,structure_b=b,primitive_cell=primitive,scale=scale,lattice_tolerance=.03,site_tolerance=.05,angle_tolerance_deg=1.0),[("structure_a",a,"/source_sha256_a"),("structure_b",b,"/source_sha256_b")],"/matched","boolean")
    def displace(self,label,a,b):
        return self.measure("motion_"+label,"MatchedPeriodicDisplacements",dict(reference_file=a,mobile_file=b),[("reference_file",a,"/reference_source_sha256"),("mobile_file",b,"/mobile_source_sha256")],"/displacements","array")
    def fraction(self,label,formula):
        self.inputs.setdefault("formulas",{})[label]=formula
        return self.measure("fractions_"+label,"CompositionFractions",{"formula":formula},[],"/formula_mass_u")
    def answer(self,name,expr,schema=None,comparison="eq",atol=1e-7,rtol=1e-6):
        if schema is None: schema={"type":"number"}
        self.props[name]=schema
        def refs(e):
            if isinstance(e,dict):
                if e.get("source")=="node": yield e["node"]
                for v in e.values(): yield from refs(v)
            elif isinstance(e,list):
                for v in e:yield from refs(v)
        nodes=list(dict.fromkeys(refs(expr)))
        self.outcomes.append({"id":name,"left":{"source":"answer","path":"/"+name},"op":comparison,"right":expr,"evidence_nodes":nodes,"atol":atol,"rtol":rtol})
    def numbers(self,name,values,integer=False):
        self.answer(name,arr(*values),{"type":"array","items":{"type":"integer" if integer else "number"},"minItems":len(values),"maxItems":len(values)})
    def booleans(self,name,values):
        self.answer(name,op("scalar_array",*values),{"type":"array","items":{"type":"boolean"},"minItems":len(values),"maxItems":len(values)})
    def rank(self,name,values,minimum=False,ids=None):
        labels=lit(ids) if ids else {"source":"inputs","path":"/sample_ids"}
        expr=op("argmin" if minimum else "argmax",op("paired_rows",labels,arr(*values)),id_path="/0",value_path="/1",tie_atol=1e-7,tie_rtol=1e-7)
        self.answer(name,expr,{"type":"array","items":{"type":"string"},"minItems":1},"set_equal")
    def finish(self,question,branches,units,conditions=None):
        self.inputs["conditions"]={"symmetry_distance_tolerance_angstrom":.01,"symmetry_angle_tolerance_deg":1.0,"geometric_match":{"primitive_cell":True,"allow_isotropic_scale":False,"fractional_lattice_tolerance":.03,"normalized_site_tolerance":.05,"angle_tolerance_deg":1.0},"powder":{"wavelength_angstrom":1.5406,"two_theta_range_deg":[5,100],"intensity_scale_maximum":100},**(conditions or {})}
        task={"id":self.id,"domain":"Material","question":question+" All supplied geometries are controlled synthetic inputs, not measured structures or claims of thermodynamic stability. Preserve sample order from sample_ids unless a field specifies pair order. Powder quantities are ideal non-anomalous kinematic values without broadening or texture; geometric edges do not establish chemical bonds. Report only the requested structured fields.","inputs":self.inputs,"files":["asset://"+x for x in self.assets],"answer_schema":{"type":"object","properties":self.props,"required":list(self.props),"additionalProperties":False},"question_language":"en","unit_annotations":units}
        task["Parameter"]=json.dumps(self.inputs,sort_keys=True)
        evaluation={"schema_version":"workflow.v1","nodes":self.nodes,"outcomes":self.outcomes,"efficiency":{"free_recovery_calls":2,"free_disambiguation_calls":0,"recovery_tools":["ReadCrystalStructure"]}}
        return {"task":task,"evaluation":evaluation,"design":{"scientific_goal":self.goal,"parallel_branches":branches,"shared_preprocessing":"Resolve each immutable structure once, retain source identity, supplied cell, occupancy and site correspondence; reuse these scientific definitions across the independent property comparisons.","early_stop_logic":self.early,"repair_opportunity":self.repair,"case_study":self.showcase,"source_notes":"Original synthetic geometries and questions authored for this draft; no external experimental dataset or third-party structure is redistributed. P1 CIF expansion is explicit. Scientific outputs must come from real deterministic tool observations."},"assets":self.assets}


NUMARR={"type":"array","items":{"type":"number"}}
OBJARR={"type":"array","items":{"type":"object"}}
CUB=lambda a:(a,a,a,90,90,90)
B2=[("Cs",0,0,0),("Cl",.5,.5,.5)]
ROCK=[(el,*p) for el,ps in [("Na",[(0,0,0),(0,.5,.5),(.5,0,.5),(.5,.5,0)]),("Cl",[(.5,0,0),(0,.5,0),(0,0,.5),(.5,.5,.5)])] for p in ps]


def build():
    studies=[]
    # 14: representation invariance separates a supercell from actual strain.
    s=Study(14,["primitive_B2","doubled_B2","tetragonal_B2"],"Distinguish cell bookkeeping from real anisotropic deformation by joining density, geometric equivalence and diffraction.",True)
    a=s.file("primitive_B2",cif(CUB(4.1),B2))
    b=s.file("doubled_B2",cif((8.2,4.1,4.1,90,90,90),[(el,(x+j)/2,y,z) for j in range(2) for el,x,y,z in B2]))
    c=s.file("tetragonal_B2",cif((4.1,4.1,4.51,90,90,90),B2))
    ds=[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],[a,b,c])]
    s.numbers("density_g_cm3",ds);s.answer("supercell_to_primitive_density_ratio",op("divide",ds[1],ds[0]))
    s.booleans("matches_to_primitive",[s.match("supercell",a,b),s.match("strain",a,c)])
    s.numbers("first_powder_angle_deg",[s.powder(k,f) for k,f in zip(s.inputs['sample_ids'],[a,b,c])])
    s.numbers("space_group_numbers",[s.symmetry(k,f) for k,f in zip(s.inputs['sample_ids'],[a,b,c])],True)
    s.repair="The doubled cell is a legitimate alternative representation: compare after primitive reduction instead of treating unequal site counts as a different phase. Keep strain physically distinct."
    studies.append(s.finish("A repository contains one B2 CsCl motif, a doubled cell, and a tetragonally strained version. Audit which distinctions are cell representation and which change scalar observables. Return density_g_cm3, supercell_to_primitive_density_ratio, matches_to_primitive for [doubled, tetragonal] under the declared geometric tolerances, first_powder_angle_deg, and space_group_numbers. Primitive reduction is allowed, isotropic rescaling is not.",["cell mass/volume accounting","geometric representation equivalence","symmetry and first powder line"],[{"fields":["density_g_cm3"],"unit":"g/cm^3"},{"fields":["first_powder_angle_deg"],"unit":"degree"}]))
    # 15: actual O distortion versus tolerance-dependent symmetry assignment.
    s=Study(15,["ideal","oxygen_displaced"],"Audit whether a geometric symmetry label is robust to distance tolerance while tracking local environment changes.",True)
    ideal=[("Sr",0,0,0),("Ti",.5,.5,.5),("O",.5,.5,0),("O",.5,0,.5),("O",0,.5,.5)]
    pert=ideal[:2]+[("O",.503,.497,.002),*ideal[3:]]
    fs=[s.file("ideal",cif(CUB(3.9),ideal)),s.file("oxygen_displaced",cif(CUB(3.9),pert))]
    s.numbers("space_groups_fine",[s.symmetry(k+"_fine",f,.001) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.numbers("space_groups_coarse",[s.symmetry(k+"_coarse",f,.05) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.numbers("density_g_cm3",[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    s.numbers("directed_edges_within_2_02_A",[s.neighbors(k,f,2.02) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.numbers("first_powder_angle_deg",[s.powder(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    s.booleans("symmetry_tolerance_independent",[op("select_if_text_equal",obs("symmetry_"+k+"_fine","/space_group_symbol"),obs("symmetry_"+k+"_coarse","/space_group_symbol"),lit(True),lit(False)) for k in s.inputs["sample_ids"]])
    s.repair="A coarse symmetry label is not a correction of atomic coordinates; retain original coordinates and analyze both declared tolerances."
    studies.append(s.finish("A cubic perovskite motif has either exact coordinates or a small single-oxygen displacement. Determine how stable its inferred symmetry is to geometric tolerance and whether bulk density or a finite-radius neighborhood reports that perturbation. Return space_groups_fine at 0.001 A, space_groups_coarse at 0.05 A (both angle tolerance 1 degree), density_g_cm3, directed_edges_within_2_02_A, first_powder_angle_deg, and symmetry_tolerance_independent (whether both declared tolerances yield the same space-group symbol). Count directed periodic image edges, including self images if they occur; exclude only the zero-image self pair. These symmetry labels are nonmagnetic geometric assignments, not evidence of a phase transition.",["fine/coarse symmetry audit","density invariant under coordinate motion","local geometry and diffraction"],[{"fields":["directed_edges_within_2_02_A"],"unit":"count"}],{"symmetry_distance_tolerances_angstrom":[.001,.05],"neighbor_cutoff_angstrom":2.02}))
    # 16: occupancies must not be silently promoted to full atoms.
    s=Study(16,["ordered_A","ordered_B","average_disorder"],"Separate occupancy-weighted density/composition from unsupported ordered-structure observables.")
    ordered=[("Na",0,0,0),("K",.5,.5,0),("Cl",.5,0,.5),("Cl",0,.5,.5)]
    alternative=[("K",0,0,0),("Na",.5,.5,0),("Cl",.5,0,.5),("Cl",0,.5,.5)]
    dis=[("Na",0,0,0,.5),("K",0,0,0,.5),("Na",.5,.5,0,.5),("K",.5,.5,0,.5),("Cl",.5,0,.5,1),("Cl",0,.5,.5,1)]
    fs=[s.file(k,cif(CUB(6.0),v)) for k,v in zip(s.inputs['sample_ids'],[ordered,alternative,dis])]
    s.numbers("density_g_cm3",[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    
    for k,f in zip(s.inputs['sample_ids'],fs): s.answer(k+"_element_amounts_per_cell",s.composition(k,f),{"type":"object"})
    read=s.read("average",fs[2]);s.answer("disordered_first_site_species",obs("read_average","/structure/sites/0/species"),{"type":"array","items":{"type":"object"},"minItems":2})
    s.numbers("ordered_directed_edge_counts",[s.neighbors(k,f,4.3) for k,f in zip(s.inputs['sample_ids'][:2],fs[:2])],True)
    s.booleans("ordered_geometric_equivalence",[s.match("domains",fs[0],fs[1])])
    s.answer("excluded_from_ordered_geometry_ids",lit(["average_disorder"]),{"type":"array","items":{"type":"string"},"minItems":1},"set_equal")
    s.outcomes[-1]['evidence_nodes']=['read_average']
    s.early="Once mixed occupancy is established, omit ordered-only diffraction, symmetry and neighbor analyses for that average record; retain its meaningful occupancy-weighted density and composition."
    s.repair="Identify a physically meaningful domain-of-applicability exclusion. Do not repair the average model by assigning all partial sites unit occupancy or inventing an ordered microstate."
    studies.append(s.finish("Two ordered cation domains and an average Na/K-disordered model describe the same nominal composition and cell. Compare density_g_cm3 and the three <sample_id>_element_amounts_per_cell objects, disordered_first_site_species with occupancies from the parsed average model, ordered_directed_edge_counts at 4.3 A for [ordered_A, ordered_B], and ordered_geometric_equivalence for that pair. Report excluded_from_ordered_geometry_ids: mixed-occupancy models must be excluded from any full-occupancy-only local or geometric equivalence calculation. Do not replace the average disorder with an invented ordered configuration.",["occupancy-weighted mass and composition","ordered domain equivalence","explicit applicability exclusion"],[{"fields":["density_g_cm3"],"unit":"g/cm^3"}],{"neighbor_cutoff_angstrom":4.3}))
    # 17: equal-density polymorphs can have distinct reciprocal/local geometry.
    s=Study(17,["bcc_Fe","fcc_Fe"],"Show why density alone cannot identify an equal-atomic-volume crystal topology.")
    ab=2.86;af=ab*2**(1/3)
    fs=[s.file("bcc_Fe",cif(CUB(ab),[("Fe",0,0,0),("Fe",.5,.5,.5)])),s.file("fcc_Fe",cif(CUB(af),[("Fe",0,0,0),("Fe",0,.5,.5),("Fe",.5,0,.5),("Fe",.5,.5,0)]))]
    s.numbers("density_g_cm3",[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    s.numbers("space_group_numbers",[s.symmetry(k,f) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.numbers("directed_edges_within_2_7_A",[s.neighbors(k,f,2.7) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.numbers("first_powder_angle_deg",[s.powder(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    s.booleans("geometric_equivalence",[s.match("polymorph",*fs)])
    studies.append(s.finish("Compare bcc and fcc iron motifs deliberately constructed with equal volume per atom. Return density_g_cm3, space_group_numbers, directed_edges_within_2_7_A, first_powder_angle_deg, and geometric_equivalence under the declared tolerances. Explain the identifiability issue numerically through these fields; no magnetic order, free energy or experimental phase assignment is implied.",["equal-volume density accounting","local coordination topology","reciprocal-space discrimination"],[{"fields":["first_powder_angle_deg"],"unit":"degree"}],{"neighbor_cutoff_angstrom":2.7}))
    # 18: topology versus interlayer packing in two carbon allotrope models.
    s=Study(18,["diamond","layered_carbon"],"Compare three-dimensional and layered carbon geometry using local contact density and reciprocal observables.")
    base=[(0,0,0),(0,.5,.5),(.5,0,.5),(.5,.5,0)]
    diamond=[("C",*p) for p in base]+[("C",*((v+.25)%1 for v in p)) for p in base]
    layer=[("C",0,0,0),("C",1/3,2/3,0),("C",0,0,.5),("C",2/3,1/3,.5)]
    fs=[s.file("diamond",cif(CUB(3.567),diamond)),s.file("layered_carbon",cif((2.46,2.46,6.7,90,90,120),layer))]
    ns=[s.neighbors(k,f,1.7) for k,f in zip(s.inputs['sample_ids'],fs)]
    s.numbers("density_g_cm3",[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    s.numbers("contacts_per_atom",[op("divide",v,obs("neighbors_"+k,"/site_count")) for k,v in zip(s.inputs['sample_ids'],ns)])
    s.numbers("first_powder_angle_deg",[s.powder(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    s.numbers("space_group_numbers",[s.symmetry(k,f) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.rank("denser_ids",[obs("density_"+k,"/density_g_per_cm3") for k in s.inputs['sample_ids']])
    studies.append(s.finish("A carbon panel contains an ideal tetrahedral network and an AB-stacked layered motif. Quantify density_g_cm3, contacts_per_atom (directed periodic contacts at 1.7 A divided by supplied-cell atom count), first_powder_angle_deg, and space_group_numbers; return denser_ids including numerical ties. Do not infer conductivity or elastic moduli from these static descriptors.",["local finite-radius contact normalization","mass packing","symmetry and low-angle diffraction"],[{"fields":["contacts_per_atom"],"unit":"dimensionless"}],{"neighbor_cutoff_angstrom":1.7}))
    # 19: substitution changes denominator as well as elemental inventory.
    s=Study(19,["LiCoO2","LiNiO2","NaCoO2"],"Compare transition-metal and alkali substitutions at fixed geometry without confusing mass and atomic fractions.")
    formulas=s.inputs['sample_ids'];fs=[]
    for k,alk,metal in [("LiCoO2","Li","Co"),("LiNiO2","Li","Ni"),("NaCoO2","Na","Co")]:
        fs.append(s.file(k,cif((2.9,2.9,10.8,90,90,120),[(alk,0,0,0),(metal,0,0,.5),("O",1/3,2/3,.25),("O",2/3,1/3,.75)])))
    masses=[s.fraction(k,k) for k in formulas];ds=[s.density(k,f) for k,f in zip(formulas,fs)]
    s.numbers("formula_mass_u",masses);s.numbers("density_g_cm3",ds)
    s.numbers("oxygen_mass_fraction",[obs("fractions_"+k,"/mass_fractions/O") for k in formulas])
    s.numbers("directed_edges_within_3_0_A",[s.neighbors(k,f,3.0) for k,f in zip(formulas,fs)],True)
    s.rank("largest_oxygen_mass_fraction_ids",[obs("fractions_"+k,"/mass_fractions/O") for k in formulas])
    studies.append(s.finish("Three layered oxide motifs share the same cell and fractional-site geometry while alkali or transition metal is substituted. Compare formula_mass_u, density_g_cm3, oxygen_mass_fraction, directed_edges_within_3_0_A, and largest_oxygen_mass_fraction_ids. Use formula mass per stated formula, not per conventional cell, and distinguish an elemental mass fraction from its atom fraction. No electrochemical capacity or stability is implied.",["formula composition fractions","fixed-cell substitution density","geometric neighborhood invariance"],[{"fields":["formula_mass_u"],"unit":"u"}],{"neighbor_cutoff_angstrom":3.0}))
    # 20: wrapped versus unwrapped coordinates do not imply a jump path.
    s=Study(20,["reference","wrapped_mobile","unwrapped_mobile"],"Audit periodic endpoint displacement invariance under equivalent fractional-coordinate representations.")
    ref=[("Na",.97,.2,.3),("Ti",.4,.4,.4),("O",.2,.65,.7)]
    wrapped=[("Na",.03,.2,.3),("Ti",.405,.4,.4),("O",.2,.65,.7)]
    unwrapped=[("Na",1.03,.2,.3),("Ti",.405,.4,.4),("O",.2,.65,.7)]
    fs=[s.file(k,cif((5,6,7,90,90,90),v)) for k,v in zip(s.inputs['sample_ids'],[ref,wrapped,unwrapped])]
    for k,f in zip(s.inputs['sample_ids'],fs):s.read(k,f)
    s.numbers("parsed_site_counts",[op("length",obs("read_"+k,"/structure/sites")) for k in s.inputs["sample_ids"]],True)
    for k,f in zip(s.inputs['sample_ids'][1:],fs[1:]):
        s.displace(k,fs[0],f)
        s.numbers(k+"_minimum_distances_A",[obs("motion_"+k,f"/displacements/{i}/minimum_distance_angstrom") for i in range(3)])
        s.answer(k+"_Na_displacement_A",obs("motion_"+k,"/displacements/0/displacement_angstrom"),{"type":"array","items":{"type":"number"},"minItems":3,"maxItems":3})
    s.numbers("directed_edges_within_3_A",[s.neighbors(k,f,3.) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.repair="Preserve the same fixed site identities; use equivalent periodic coordinates rather than interpreting a wrapped coordinate difference as a large physical displacement. No trajectory unwrapping is justified from endpoints alone."
    studies.append(s.finish("The same mobile endpoint is supplied with Na either wrapped into the unit cell or written outside it. Atom correspondence is fixed by the species sequence Na,Ti,O in every file, and the cell is unchanged. Return wrapped_mobile_minimum_distances_A and unwrapped_mobile_minimum_distances_A in that fixed atom order, wrapped_mobile_Na_displacement_A and unwrapped_mobile_Na_displacement_A (Cartesian mobile-image minus reference), parsed_site_counts, and directed_edges_within_3_A for every sample. Use exact minimum-image geometry, not raw fractional subtraction. This is an endpoint comparison, not a diffusion coefficient or pathway.",["shared fixed-identity geometry audit","two endpoint displacement representations","periodic neighborhood invariance"],[{"fields":["wrapped_mobile_minimum_distances_A","unwrapped_mobile_minimum_distances_A"],"unit":"angstrom"}],{"neighbor_cutoff_angstrom":3.0}))
    # 21: equal minimum distances need not define a unique direction.
    s=Study(21,["reference","half_cell","near_half_cell"],"Resolve minimum-image degeneracy honestly instead of presenting a convention-selected vector as uniquely physical.")
    fs=[s.file(k,cif(CUB(5),v)) for k,v in zip(s.inputs['sample_ids'],[[('Cs',0,0,0),('Cl',.2,.3,.4)],[('Cs',.5,0,0),('Cl',.21,.3,.4)],[('Cs',.499,0,0),('Cl',.21,.3,.4)]])]
    for k,f in zip(s.inputs['sample_ids'],fs):s.read(k,f)
    s.numbers("parsed_site_counts",[op("length",obs("read_"+k,"/structure/sites")) for k in s.inputs["sample_ids"]],True)
    for k,f in zip(s.inputs['sample_ids'][1:],fs[1:]):
        s.displace(k,fs[0],f)
        s.numbers(k+"_minimum_distances_A",[obs("motion_"+k,f"/displacements/{i}/minimum_distance_angstrom") for i in range(2)])
        s.numbers(k+"_image_tie_counts",[obs("motion_"+k,f"/displacements/{i}/tie_count") for i in range(2)],True)
        s.booleans(k+"_unique",[obs("motion_"+k,f"/displacements/{i}/minimum_image_unique") for i in range(2)])
    s.numbers("density_g_cm3",[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    studies.append(s.finish("Two fixed-identity endpoints place Cs exactly, or nearly, halfway across a cubic cell; Cl undergoes a small unambiguous displacement. Return half_cell_minimum_distances_A, near_half_cell_minimum_distances_A, half_cell_image_tie_counts, near_half_cell_image_tie_counts, half_cell_unique, near_half_cell_unique, all in [Cs,Cl] order, density_g_cm3 and parsed_site_counts for every sample. Images within 1e-8 A of the shortest distance count as tied. A deterministic vector tie convention cannot establish a unique physical direction.",["fixed atom identities","exact versus near-degenerate periodic endpoints","mass-density control"],[{"fields":["half_cell_minimum_distances_A","near_half_cell_minimum_distances_A"],"unit":"angstrom"}],{"minimum_image_tie_tolerance_angstrom":1e-8}))
    # 22: a poor lattice basis requires periodic images beyond a 27-cell stencil.
    s=Study(22,["oblique_basis","reduced_basis"],"Check basis invariance when short physical neighbors require large integer image shifts.",True)
    a=s.file("oblique_basis",poscar([[4,0,0],[11.8,.7,0],[0,0,6]],["He"],[1],[[0,0,0]]),"vasp")
    b=s.file("reduced_basis",poscar([[4,0,0],[-.2,.7,0],[0,0,6]],["He"],[1],[[0,0,0]]),"vasp")
    fs=[a,b];ds=[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)]
    s.numbers("density_g_cm3",ds)
    s.numbers("directed_edges_within_1_A",[s.neighbors(k,f,1.) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.numbers("space_group_numbers",[s.symmetry(k,f) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.booleans("same_periodic_structure",[s.match("basis",a,b)])
    s.read("oblique",a);s.read("reduced",b)
    s.numbers("cell_volumes_A3",[obs("read_"+k,"/structure/lattice/volume") for k in ["oblique","reduced"]])
    # Require full image vectors, distances and displacements so a count-only stencil cannot pass.
    for k in s.inputs['sample_ids']:
        s.answer(k+"_edges",obs("neighbors_"+k,"/neighbors"),{"type":"array","items":{"type":"object"},"minItems":1},comparison="multiset_equal")
    s.repair="Replace the inadequate image-search representation with exact periodic geometry or an equivalent reduced basis; do not change the lattice itself. The two POSCARs differ by an integer unimodular basis transform."
    studies.append(s.finish("An elongated oblique lattice basis and an integer-reduced basis describe the same one-site He lattice. Test basis invariance using density_g_cm3, directed_edges_within_1_A, space_group_numbers same_periodic_structure and cell_volumes_A3. Also return oblique_basis_edges and reduced_basis_edges: complete directed edge records containing center_index, neighbor_index, image_shift, distance_angstrom, displacement_angstrom and edge_id, with image shifts expressed in each supplied basis. Count nonzero self images. A fixed 27-cell search is not assumed adequate. These compressed synthetic motifs illustrate geometry, not stable helium phases.",["basis-independent density and symmetry","exact periodic image enumeration in each basis","integer-basis equivalence"],[{"fields":["oblique_basis_edges","reduced_basis_edges"],"unit":"angstrom for distances and vectors; integer image shifts"}],{"neighbor_cutoff_angstrom":1.0}))
    # 23: geometric scaling flags have physical consequences.
    s=Study(23,["reference","isotropic_compression","orthorhombic_strain"],"Disentangle volume scaling, shape strain and normalized geometric equivalence.")
    motif=[('Mg',0,0,0),('O',.5,.5,.5)]
    fs=[s.file(k,cif(cell,motif)) for k,cell in zip(s.inputs['sample_ids'],[CUB(3.5),CUB(3.15),(3.15,3.5,3.85,90,90,90)])]
    ds=[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)];s.numbers("density_g_cm3",ds)
    s.numbers("density_relative_to_reference",[op("divide",v,ds[0]) for v in ds])
    s.booleans("matches_without_rescaling",[s.match(k+"_physical",fs[0],f) for k,f in zip(s.inputs['sample_ids'][1:],fs[1:])])
    s.booleans("matches_allowing_isotropic_rescaling",[s.match(k+"_scaled",fs[0],f,scale=True) for k,f in zip(s.inputs['sample_ids'][1:],fs[1:])])
    s.numbers("directed_edges_within_3_A",[s.neighbors(k,f,3.) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    studies.append(s.finish("A two-species crystal motif is isotropically compressed or strained along unequal axes while fractional sites are fixed. Return density_g_cm3, density_relative_to_reference, matches_without_rescaling and matches_allowing_isotropic_rescaling for [isotropic_compression, orthorhombic_strain], and directed_edges_within_3_A for all samples. Use the declared geometric tolerances; the second match comparison permits isotropic volume scaling, the first preserves physical lengths. A scale-normalized match does not imply equal mass density or thermodynamic state.",["physical density ratios","two scientifically distinct equivalence conventions","finite-radius contact changes"],[{"fields":["density_relative_to_reference"],"unit":"dimensionless"}],{"neighbor_cutoff_angstrom":3.0}))
    # 24: isostructural substitution is neither chemical identity nor diffraction identity.
    s=Study(24,["MgO","CaO","MgS"],"Screen isostructural chemistry using explicit composition, density and low-angle powder contrasts.")
    fs=[]
    for k,metal,anion,length in [("MgO","Mg","O",4.21),("CaO","Ca","O",4.81),("MgS","Mg","S",5.2)]:
        sites=[(metal if el=='Na' else anion,x,y,z) for el,x,y,z in ROCK];fs.append(s.file(k,cif(CUB(length),sites)))
    masses=[s.fraction(k,k) for k in s.inputs['sample_ids']]
    ds=[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)];s.numbers("density_g_cm3",ds)
    s.numbers("formula_mass_u",masses)
    s.numbers("first_powder_angle_deg",[s.powder(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    s.numbers("space_group_numbers",[s.symmetry(k,f) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.rank("densest_ids",ds)
    s.rank("smallest_first_angle_ids",[obs("powder_"+k,"/peaks/0/two_theta_deg") for k in s.inputs['sample_ids']],True)
    studies.append(s.finish("A rocksalt-type panel replaces cation, anion and lattice length. Compare formula_mass_u, density_g_cm3, first_powder_angle_deg and space_group_numbers; return densest_ids and smallest_first_angle_ids with ties. This screening asks whether an isostructural label alone determines either density ranking or first-line position. Do not infer equal chemical composition from equal space-group numbers.",["elemental mass accounting","density screening","symmetry versus reciprocal-length discrimination"],[{"fields":["density_g_cm3"],"unit":"g/cm^3"}]))
    # 25: paired vacancies preserve reduced formula while changing cell inventory.
    s=Study(25,["perfect","paired_vacancy","Ca_substitution"],"Detect information lost by reduced formulas in vacancy and substitution models.")
    perfect=[('Mg' if el=='Na' else 'O',x,y,z) for el,x,y,z in ROCK]
    defect=[v for i,v in enumerate(perfect) if i not in [0,4]]
    doped=[('Ca',*perfect[0][1:]),*perfect[1:]]
    fs=[s.file(k,cif(CUB(4.21),v)) for k,v in zip(s.inputs['sample_ids'],[perfect,defect,doped])]
    ds=[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)]
    s.numbers("density_g_cm3",ds)
    for k,f in zip(s.inputs['sample_ids'],fs): s.answer(k+"_element_amounts_per_cell",s.composition(k,f),{"type":"object"})
    s.numbers("directed_edges_within_2_2_A",[s.neighbors(k,f,2.2) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.numbers("parsed_site_counts",[obs("density_"+k,"/sites") for k in s.inputs['sample_ids']],True)
    s.answer("vacancy_mass_density_fraction",op("divide",ds[1],ds[0]))
    s.rank("lowest_density_ids",ds,True)
    studies.append(s.finish("One MgO cell is complete, another removes a specified Mg/O pair, and the third replaces one Mg with Ca. The cell vectors and all retained coordinates are fixed. Return density_g_cm3, the three <sample_id>_element_amounts_per_cell objects, parsed_site_counts, directed_edges_within_2_2_A, vacancy_mass_density_fraction relative to perfect, and lowest_density_ids. Use occupancy-weighted atom amounts in the actual supplied cell, not only reduced chemical formulas; do not assign defect formation energies or electronic charge states.",["cell inventory versus reduced formula","vacancy/substitution mass-density effects","local geometric contact loss"],[{"fields":["element_amounts_per_cell"],"unit":"atoms per supplied cell"}],{"neighbor_cutoff_angstrom":2.2}))
    # 26: wavelength moves angles, not the reciprocal lattice.
    s=Study(26,["NaCl","CsCl"],"Compare wavelength-dependent diffraction angles with wavelength-independent lattice d spacings.")
    fs=[s.file("NaCl",cif(CUB(5.64),ROCK)),s.file("CsCl",cif(CUB(4.12),B2))]
    for label,wave in [('Cu',1.5406),('Mo',.71073)]:
        s.numbers(label+"_first_angle_deg",[s.powder(k+"_"+label,f,wave) for k,f in zip(s.inputs['sample_ids'],fs)])
        s.numbers(label+"_first_d_A",[obs("powder_"+k+"_"+label,"/peaks/0/d_spacing_angstrom") for k in s.inputs['sample_ids']])
    s.numbers("density_g_cm3",[s.density(k,f) for k,f in zip(s.inputs['sample_ids'],fs)])
    s.numbers("space_group_numbers",[s.symmetry(k,f) for k,f in zip(s.inputs['sample_ids'],fs)],True)
    s.numbers("first_d_Cu_over_Mo",[op("divide",obs("powder_"+k+"_Cu","/peaks/0/d_spacing_angstrom"),obs("powder_"+k+"_Mo","/peaks/0/d_spacing_angstrom")) for k in s.inputs['sample_ids']])
    studies.append(s.finish("For two chemically distinct cubic salt motifs, compare ideal powder diffraction at wavelengths 1.5406 A (Cu label) and 0.71073 A (Mo label), using 2theta from 5 to 100 degrees. Return Cu_first_angle_deg, Mo_first_angle_deg, Cu_first_d_A, Mo_first_d_A, first_d_Cu_over_Mo, density_g_cm3 and space_group_numbers. First means the smallest-angle nonzero-intensity line within the declared range; verify this compares the same lowest-order reflection rather than assuming all restricted ranges do. Scalar powder intensities here use ordinary real atomic scattering factors.",["two wavelength-specific diffraction branches","reciprocal-spacing comparison","independent density and symmetry identity controls"],[{"fields":["Cu_first_d_A","Mo_first_d_A"],"unit":"angstrom"}],{"powder_wavelengths_angstrom":[1.5406,.71073]}))
    return studies
