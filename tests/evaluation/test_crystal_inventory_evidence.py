"""Unit-cell populations and fractional sites cannot become guessed formulas."""
import pytest
from evaluation.workflow.crystals import crystal_element_inventory, crystal_density_inventory
from evaluation.workflow.values import MissingEvidence


def site(**species):return {'species':[{'element':e,'occu':n}for e,n in species.items()]}


def test_inventory_preserves_cell_multiplicity_not_reduced_formula():
    value={'structure':{'sites':[site(Cs=1),site(Cl=1),site(Cs=1),site(Cl=1)]}}
    assert crystal_element_inventory(value)=={'Cs':2,'Cl':2}


def test_disorder_and_vacancy_occupancy_are_not_renormalized():
    value={'structure':{'sites':[site(Na=.25,K=.25),site(Cl=.5)]}}
    assert crystal_element_inventory(value)=={'Na':.25,'K':.25,'Cl':.5}


@pytest.mark.parametrize('value',[
    {'formula':'CsCl'},
    {'structure':{'sites':[site(Na=.7,K=.6)]}},
    {'structure':{'sites':[site(Na=True)]}},
    {'structure':{'sites':[site(Na=float('inf'))]}},
    {'element_amounts':{'Na':1},'structure':{'sites':[site(Na=.5)]}},
    {'element_amounts':{'Na':1},'structure':{'sites':[site(Cl=1)]}},
])
def test_missing_invalid_or_conflicting_source_inventory_is_rejected(value):
    with pytest.raises(MissingEvidence):crystal_element_inventory(value)


def test_consistent_dual_source_views_are_checked():
    assert crystal_element_inventory({'element_amounts':{'Na':.5},'structure':{'sites':[site(Na=.5)]}})=={'Na':.5}


def density_receipt(formula='K0.15 Na0.45 Cl1', sites=2):
    return dict(formula=formula, sites=sites, mass_u=51.663141176,
                volume_angstrom_cubed=125., density_g_per_cm3=51.663141176*1.66053906660/125.,
                source_file='observed.cif', source_sha256='a'*64,
                method='pymatgen static periodic-cell density; occupancy-weighted cell mass / cell volume')


def test_density_cell_formula_preserves_fractional_population_and_cell_multiplicity():
    assert crystal_density_inventory(density_receipt()) == {'K':.15,'Na':.45,'Cl':1.}
    assert crystal_density_inventory(density_receipt('Cs2 Cl2',4)) == {'Cs':2.,'Cl':2.}
    # Never multiply a reduced formula by the site count, or renormalize vacancies.
    assert crystal_density_inventory(density_receipt('Cs1 Cl1',4)) == {'Cs':1.,'Cl':1.}


@pytest.mark.parametrize('change',[
    {'formula':'CsCl'}, {'formula':'Na0 Cl1'}, {'formula':'Na-1 Cl1'},
    {'formula':'Na1 Na1'}, {'formula':'Na2 Cl2'}, {'formula':'Na1e0 Cl1'},
    {'source_sha256':'wrong'}, {'sites':True}, {'sites':1},
    {'mass_u':float('inf')}, {'density_g_per_cm3':3},
    {'method':'molecular formula'}, {'element_amounts':{'Na':1.,'Cl':1.}},
])
def test_density_inventory_requires_consistent_complete_source_receipt(change):
    value=density_receipt();value.update(change)
    with pytest.raises(MissingEvidence):crystal_density_inventory(value)


def test_arbitrary_formula_object_cannot_be_promoted_to_density_cell_inventory():
    with pytest.raises(MissingEvidence):crystal_density_inventory({'formula':'Na1 Cl1'})
