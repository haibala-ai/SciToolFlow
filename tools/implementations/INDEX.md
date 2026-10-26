# 科学实现模块索引

公开绑定来自当前唯一catalog；未直接注册的模块为共享依赖或既有内部适配，不因此自动视为可调用的公开工具。名称和输入输出以catalog为准。

## 跨领域适配

| 模块 | 公开工具／辅助职责 |
| --- | --- |
| [adapters.py](adapters.py) | `DNAMolecularWeight`, `GenerateMolecularConformer`, `NucleicAcidGCCalculator`, `SequenceSimilarityCalculator` |

## chemistry

| 模块 | 公开工具／辅助职责 |
| --- | --- |
| [chemspider_current.py](chemistry/chemspider_current.py) | `InChIToCSID` |
| [core.py](chemistry/core.py) | `CountMolecularAtoms`, `MolecularCentroid` |
| [electronic_descriptors.py](chemistry/electronic_descriptors.py) | `MolecularElectronicDescriptors` |
| [fingerprints.py](chemistry/fingerprints.py) | `ClusterMolecularFingerprints`, `CompareMolecularFingerprints`, `MolecularFingerprint` |
| [functional_groups.py](chemistry/functional_groups.py) | `FuncGroups` |
| [identifiers.py](chemistry/identifiers.py) | `PubChemSafety`, `QueryMoleculeCatalog`, `ResolveChemicalIdentifier` |
| [ml.py](chemistry/ml.py) | Retired CSV model adapters; use the explicit current catalog contracts. Legacy filename inference, implicit label binning and zero imputation are removed. These names are not publi |
| [molecular_analysis.py](chemistry/molecular_analysis.py) | `AtomPairCodes`, `CompareMolecularShapes`, `EStateAnalysis`, `InspectSELFIES`, `InspectTautomerQuery`, `MolecularFormalCharges`, `MolecularKey`, `NormalizedPrincipalMoments`, `RDKitCapabilities`, `SubstructureQuery` |
| [molecular_operations.py](chemistry/molecular_operations.py) | `AddWavyStereoBonds`, `AssignChiralTagsFromCoordinates`, `CondenseAbbreviations`, `InspectQueryHydrogens`, `MergeQueryHydrogens` |
| [molecular_utilities.py](chemistry/molecular_utilities.py) | `CalculateEstateVsa`, `CheckValidRingCut`, `ConvertSdfToCsv`, `CreateShingling`, `Deprotect`, `Enumerate`, `ExplainAtomPairScore`, `ExtractRotatableDihedralsFromSdf`, `GenerateFraggleFragments`, `GenerateRandomSELFIES`, `GetConnectivityInvariants`, `GetFeatureInvariants`, `GetFraggleSimilarity`, `GetMolFrags`, `GetRingSystems`, `InChIToInChIKey`, `InChIToSMILES`, `IsValidInChIKey`, `PerceiveBondsFromCoordinates`, `SELFIEStoSMILES`, `SMILESToInChI`, `SMILESToWeight`, `SMILEStoSELFIES`, `ShowMol`, `SlnToSmiles`, `TestMolecule` |
| [novopro.py](chemistry/novopro.py) | 辅助实现；由上层模块导入。 |
| [rdkit_basic.py](chemistry/rdkit_basic.py) | `AssignCIPLabels`, `GetAliphaticCarbocyclesNum`, `GetAliphaticHeterocyclesNum`, `GetAliphaticRingsNum`, `GetAmideBondsNum`, `GetAromaticCarbocyclesNum`, `GetAromaticHeterocyclesNum`, `GetAromaticRingsNum`, `GetAsphericity`, `GetAtomStereoCentersNum`, `GetAutocorrelation2D`, `GetAutocorrelation3D`, `GetBCUT`, `GetBridgeheadAtomsNum`, `GetChi0n`, `GetChi0v`, `GetChi1n`, `GetChi1v`, `GetChi2n`, `GetChi2v`, `GetChi3n`, `GetChi3v`, `GetChi4n`, `GetChi4v`, `GetCoulombMat`, `GetEEMCharges`, `GetEccentricity`, `GetExactMolceularWeight`, `GetFractionCSP3`, `GetGETAWAY`, `GetHBANum`, `GetHBDNum`, `GetHallKierAlpha`, `GetHeterocyclesNum`, `GetInertialShapeFactor`, `GetKappa1`, `GetKappa2`, `GetKappa3`, `GetLabuteASA`, `GetLipinskiHBANum`, `GetLipinskiHBDNum`, `GetMORSE`, `GetMolFormula`, `GetRingsNum`, `GetRotatableBondsNum`, `GetSaturatedCarbocyclesNum`, `GetSaturatedHeterocyclesNum`, `GetSaturatedRingsNum`, `GetSpiroAtomsNum`, `GetUnspecifiedAtomStereoCentersNum` |
| [rdkit_descriptors.py](chemistry/rdkit_descriptors.py) | `AssignPattyTypes` |
| [rdkit_properties.py](chemistry/rdkit_properties.py) | `AddHydrogens`, `AssignOxidationNumbers`, `AssignRadicals`, `AssignStereoChemistry`, `CalculatePBF`, `CalculatePMI1`, `CalculatePMI2`, `CalculatePMI3`, `CalculatePhi`, `CalculateRDF`, `CalculateRadiusOfGyration`, `CalculateSpherocityIndex`, `CalculateTPSA`, `CalculateWHIM`, `GetAdjacencyMatrix`, `GetAtomFeature`, `GetDistanceMatrix`, `GetHybridization`, `GetUSR`, `GetUSRCAT`, `HapticBondsToDative`, `Kekulize`, `MurckoDecompose`, `RemoveHydrogens`, `RemoveStereochemistry`, `SetAromaticity`, `SetBondStereoFromDirections` |
| [research_workflows.py](chemistry/research_workflows.py) | `CanonicalMolecularIdentity` |
| [rxn4chem_ncbi.py](chemistry/rxn4chem_ncbi.py) | 辅助实现；由上层模块导入。 |
| [rxn_sandbox_local.py](chemistry/rxn_sandbox_local.py) | `PredictReactionProducts`, `RXNPredictProperties`, `RXNRetrosynthetic` |
| [utils.py](chemistry/utils.py) | 辅助实现；由上层模块导入。 |

## materials

| 模块 | 公开工具／辅助职责 |
| --- | --- |
| [basic_local.py](materials/basic_local.py) | `CalculateDensity`, `Convert3DMolecules2SMILES`, `UnitConverter` |
| [common.py](materials/common.py) | 辅助实现；由上层模块导入。 |
| [core_structure.py](materials/core_structure.py) | `GetStructureByMaterialId` |
| [extensions.py](materials/extensions.py) | 辅助实现；由上层模块导入。 |
| [local_queries.py](materials/local_queries.py) | `CASToPrice`, `CalculateSymmetry`, `GetElementComposition`, `GetFloatingSolventMolecules`, `GetMOFLinkerSMILES`, `GetSymbolOfSite`, `GetTerminalIndices`, `MofBranchPoints`, `MofBridges`, `MofFractionalCoordinates`, `MofLattice`, `MofNeighborIndices`, `PlotAdjacencyMatrix`, `ReadCrystalStructure` |
| [material_queries.py](materials/material_queries.py) | `GetAdjPairsByBatteryId`, `GetAlloyPairsByMaterialId`, `GetAuthorsByMaterialId`, `GetAverageOxidationStatesByMaterialId`, `GetAverageVoltageByBatteryId`, `GetBatteryFormulaByBatteryId`, `GetBondLengthStatsByMaterialId`, `GetBondTypesByMaterialId`, `GetCapacityGravByBatteryId`, `GetCapacityVolByBatteryId`, `GetChargeByMoleculeId`, `GetChemicalSystemByMaterialId`, `GetChemsysByBatteryId`, `GetChemsysByMoleculeId`, `GetCompositionByMaterialId`, `GetCompositionByMoleculeId`, `GetConstituentMoleculesByMoleculeId`, `GetCoordHashByMoleculeId`, `GetCoordinationEnvsAnonymousByMaterialId`, `GetCoordinationEnvsByMaterialId`, `GetCreatedTimeByMaterialId`, `GetDeprecatedByMoleculeId`, `GetDeprecationReasonsByMoleculeId`, `GetElectrodeObjectByBatteryId`, `GetElementsByBatteryId`, `GetElementsByMaterialId`, `GetElementsByMoleculeId`, `GetEnergyAboveHullByMaterialId`, `GetEnergyGravByBatteryId`, `GetEnergyVolumeByBatteryId`, `GetEntriesCompositionSummaryByBatteryId`, `GetEosInfoByMaterialId`, `GetEquilibriumReactionEnergyPerAtom`, `GetFormulaAlphabeticalByMoleculeId`, `GetFormulaAnonymousByBatteryId`, `GetFormulaAnonymousByMoleculeId`, `GetFormulaChargeByBatteryId`, `GetFormulaDischargeByBatteryId`, `GetFormulaPrettyByMoleculeId`, `GetFracaChargeByBatteryId`, `GetFrameworkByBatteryId`, `GetFrameworkFormulaByBatteryId`, `GetFreeEnergyByMoleculeId`, `GetHostStructureByBatteryId`, `GetIdChargeByBatteryId`, `GetIdDischargeByBatteryId`, `GetInchiByMoleculeId`, `GetInchikeyByMoleculeId`, `GetLastUpdatedTimeByMoleculeId`, `GetLastUpdatedTimeByTaskId`, `GetMaterialAnonymousFormula`, `GetMaterialBandGap`, `GetMaterialCBM`, `GetMaterialDensity`, `GetMaterialDeprecationStatus`, `GetMaterialDescription`, `GetMaterialElectronicPermittivity`, `GetMaterialEnergyPerAtom`, `GetMaterialFermiEnergy`, `GetMaterialFormationEnergyPerAtom`, `GetMaterialFormula`, `GetMaterialIdByBatteryId`, `GetMaterialInitialStructures`, `GetMaterialIonicPermittivity`, `GetMaterialMagneticStatus`, `GetMaterialMetallicStatus`, `GetMaterialPackingVolume`, `GetMaterialPermittivity`, `GetMaterialStabilityStatus`, `GetMaterialVBM`, `GetMaterialVolume`, `GetMaterialXASSpectrum`, `GetMaxDeltaVolumeBatteryId`, `GetMaxVoltageStepByBatteryId`, `GetMolecularElectronicEnergy`, `GetMolecularFrequencies`, `GetMolecularThermalEnthalpy`, `GetMoleculeIdByFormula`, `GetMoleculeLevelsOfTheoryByMoleculeId`, `GetNatomsByMoleculeId`, `GetNelectronsByMoleculeId`, `GetNelementsByBatteryId`, `GetNelementsByMoleculeId`, `GetNsitesByMaterialId`, `GetNumMagneticSitesByMaterialId`, `GetNumberOfElementsByMaterialId`, `GetOpenShellByMoleculeId`, `GetOrbitalsLevelsOfTheoryByMoleculeId`, `GetOrbitalsPropertyIdsByMoleculeId`, `GetOriginsByMoleculeId`, `GetPhononInfoByMaterialId`, `GetPossibleSpeciesByMaterialId`, `GetPossibleValencesByMaterialId`, `GetPropertyIdByMoleculeId`, `GetPropertyNameByMoleculeId`, `GetReferencesByMaterialId`, `GetRemarksByMaterialId`, `GetSimilarMoleculesByMoleculeId`, `GetSpeciesHashByMoleculeId`, `GetSpinMultiplicityByMoleculeId`, `GetStabilityChargeByBatteryId`, `GetStabilityDischargeByBatteryId`, `GetStructureGraphByMaterialId`, `GetSurfaceAnisotropyByMaterialId`, `GetSymmetryByMaterialId`, `GetSymmetryByMoleculeId`, `GetSynthesisDocByKeywords`, `GetThermoLevelsOfTheoryByMoleculeId`, `GetThermoPropertyIdsByMoleculeId`, `GetTotalEntropyByMoleculeId`, `GetTotalMagnetizationByMaterialId`, `GetTotalMagnetizationNormalizedFormulaUnitsByMaterialId`, `GetTotalMagnetizationNormalizedVolByMaterialId`, `GetUncorrectedEnergyPerAtomByMaterialId`, `GetUniqueCalcTypesByMoleculeId`, `GetUniqueLevelsOfTheoryByMoleculeId`, `GetUniqueLotSolventsByMoleculeId`, `GetUniqueSolventsByMoleculeId`, `GetUniqueTaskTypesByMoleculeId`, `GetVibrationLevelsOfTheoryByMoleculeId`, `GetVibrationPropertyIdsByMoleculeId`, `GetWarningsByBatteryId`, `GetWarningsByMoleculeId`, `GetWeightedSurfaceEnergyByMaterialId`, `GetWorkingIonByBatteryId`, `GetZeroPointEnergyByMoleculeId`, `ReadQChemFrequencyModes`, `ReadQChemIRActivities`, `ReadQChemIRIntensities`, `ReadQChemNBOPopulations`, `ReadQChemRotationalEnthalpy`, `ReadQChemRotationalEntropy`, `ReadQChemTranslationalEnthalpy`, `ReadQChemTranslationalEntropy`, `ReadQChemVibrationalEnthalpy`, `ReadQChemVibrationalEntropy`, `ResolveChargeDensityMetadata`, `SearchMaterials` |
| [materials_project.py](materials/materials_project.py) | 辅助实现；由上层模块导入。 |
| [mof_stability_local.py](materials/mof_stability_local.py) | `PredictStability` |
| [raspa_local.py](materials/raspa_local.py) | `PredictAdsorption` |
| [research_workflows.py](materials/research_workflows.py) | `CompositionFractions`, `CrystalStructureMatch`, `MatchedPeriodicDisplacements`, `PeriodicNeighborList`, `PowderDiffractionPattern` |

## biology

| 模块 | 公开工具／辅助职责 |
| --- | --- |
| [blast_current.py](biology/blast_current.py) | `PerformBlastQuery` |
| [chroma_design.py](biology/chroma_design.py) | `DesignProteinChroma` |
| [common.py](biology/common.py) | `ComputeExtinctionCoefficient`, `GenerateRandomMutation` |
| [count_model.py](biology/count_model.py) | `FitBulkRNASeqCounts` |
| [deeptmhmm_local.py](biology/deeptmhmm_local.py) | `DeepTMHMM` |
| [esmfold_local.py](biology/esmfold_local.py) | `SequenceToPdb` |
| [expasy_current.py](biology/expasy_current.py) | `ScanHamap`, `Sulfinator` |
| [extensions.py](biology/extensions.py) | `CalculateAtomDistance`, `CalculateCenterOfMass`, `CalculateMolecularWeight`, `GetReverseComplement` |
| [force_gpt.py](biology/force_gpt.py) | `PredictNormalizedProteinMechanics` |
| [hippie_local.py](biology/hippie_local.py) | `HIPPIE` |
| [human_go_annotations.py](biology/human_go_annotations.py) | `GetHumanGOAnnotations` |
| [model_adapters.py](biology/model_adapters.py) | `GenerateMoleculeDescription`, `PredictHumanDrugTargetInteraction`, `PredictHumanProteinPairInteraction`, `PredictProteinSolubility`, `PredictYeastProteinPairInteraction`, `TexToMoleculeSELFIES` |
| [model_cache.py](biology/model_cache.py) | Bounded process-local *resource* reuse; never cache scientific predictions. |
| [musite_current.py](biology/musite_current.py) | `MusiteDeep` |
| [mutabind2_local.py](biology/mutabind2_local.py) | `PDBInterfaceContacts` |
| [myristoylation_current.py](biology/myristoylation_current.py) | `PredictMyristoylation` |
| [neemo_current.py](biology/neemo_current.py) | `NeEMO` |
| [novopro.py](biology/novopro.py) | `AlanineScanningLibraryDesign`, `CDRLabelingAntibody`, `CalculateAminoAcidbyDegenerateCodon`, `CompareSequenceByLogExpectation`, `ComputeAffinity`, `CpGIslandPrediction`, `DegenerateCodonCalculatorbyAminoAcid`, `ORFFind`, `OverlapPeptideLibraryDesign`, `PCRPrimerProperties`, `PalindromicSequencesFinder`, `PositionalScanningLibraryDesign`, `PredictSignalPeptide`, `SummaryEnzymeCleavageSites`, `TranslateDNAtoAminoAcidSequence`, `TruncationLibraryDesign` |
| [novopro_current.py](biology/novopro_current.py) | `CircularDNAAlignment`, `InherentDisorderedRegionsPredictor`, `PredictTransmembraneRegion`, `ProteinMotifAnalysis` |
| [novopro_primitives.py](biology/novopro_primitives.py) | `AntibodyDomainMetadata`, `FindSequenceRepeats`, `OligonucleotideAbsorbanceProperties`, `OligonucleotideMeltingTemperature`, `OptimizeCodons`, `PredictNuclearLocalization`, `ProteinHydrophilicityProfile` |
| [oma_orthologs.py](biology/oma_orthologs.py) | `GetCoronaOrthologs` |
| [omegafold_local.py](biology/omegafold_local.py) | `FoldProtein` |
| [peptide_molecule.py](biology/peptide_molecule.py) | `ConvertingPeptide2SMILES` |
| [ppi3d_current.py](biology/ppi3d_current.py) | `PPI3DPDB`, `SearchPPI3DInterfaces` |
| [protein_descriptors.py](biology/protein_descriptors.py) | `ProteinGRAVY`, `ProteinIsoelectricPointCalculator` |
| [protein_records.py](biology/protein_records.py) | `FetchPDBCoordinateFile`, `SearchProteinSequencesByName` |
| [protein_tools.py](biology/protein_tools.py) | `AnalyzeProteinCATHFromPDBID`, `AnalyzeProteinStructure`, `CalculateProteinANM` |
| [research_workflows.py](biology/research_workflows.py) | `DiversityIndices`, `ExtractPDBCoordinates`, `InspectPDBQuality`, `ParseFASTARecords`, `SequenceQualityMetrics`, `TraverseOntologyRelations` |
| [sequence_indices.py](biology/sequence_indices.py) | `ProteinAliphaticIndex`, `ProteinInstabilityIndex`, `ProteinNTerminalHalfLife` |
| [sequence_primitives.py](biology/sequence_primitives.py) | `PairwiseSequenceAlignment`, `SequenceComposition` |
| [sequence_utilities_local.py](biology/sequence_utilities_local.py) | `DigestProtein`, `DrawProteinStructure`, `GenerateRandSequence`, `RedundancyReduction` |
| [tree_distances.py](biology/tree_distances.py) | `ParseNewickTreeDistances` |

## machine_learning

| 模块 | 公开工具／辅助职责 |
| --- | --- |
| [binomial_distribution.py](machine_learning/binomial_distribution.py) | `BinomialProbabilityTable` |
| [classification.py](machine_learning/classification.py) | `TrainAndPredictClassifier` |
| [family_statistics.py](machine_learning/family_statistics.py) | `AdjustPValues`, `HypergeometricEnrichment` |
| [file_enrichment.py](machine_learning/file_enrichment.py) | Explicit file-based set enrichment,independent of gene selection or annotation. |
| [file_statistics.py](machine_learning/file_statistics.py) | File-based statistical transformations preserving complete hypothesis families. |
| [finite_population.py](machine_learning/finite_population.py) | `FinitePopulationCoverage` |
| [graph_laplacian.py](machine_learning/graph_laplacian.py) | `GraphLaplacian` |
| [hermite_interpolation.py](machine_learning/hermite_interpolation.py) | `CubicHermiteInterpolate` |
| [linear_program.py](machine_learning/linear_program.py) | `SolveLinearProgram` |
| [mantel.py](machine_learning/mantel.py) | `MantelCorrelation` |
| [matched_coordinate_distances.py](machine_learning/matched_coordinate_distances.py) | `RigidSuperposition` |
| [matrix_exponential.py](machine_learning/matrix_exponential.py) | `MatrixExponential` |
| [matrix_operations.py](machine_learning/matrix_operations.py) | `MatrixMultiply` |
| [normal_distribution.py](machine_learning/normal_distribution.py) | `StandardNormalDistribution` |
| [numeric_tools.py](machine_learning/numeric_tools.py) | `BootstrapMeanInterval`, `ChiSquareIndependence`, `ClassificationMetrics`, `CrossValidateRegressor`, `DBSCANClustering`, `DescribeNumericData`, `FiniteDifferenceGradient`, `FitLinearRegression`, `FitLogisticRegression`, `FitRidgeRegression`, `InterpolateLinear`, `KMeansClustering`, `LinearLeastSquares`, `MannWhitneyUTest`, `MatrixInverse`, `MatrixSVD`, `MedianImputeFeatures`, `MinMaxScaleFeatures`, `NumericalTrapezoidIntegration`, `OneWayANOVA`, `PairedTTest`, `PearsonCorrelation`, `PolynomialFeaturesTransform`, `PolynomialLeastSquaresFit`, `PredictLinearModel`, `PredictLogisticModel`, `PrincipalComponentProjection`, `RegressionMetrics`, `SolveLinearSystem`, `SpearmanCorrelation`, `SplitTrainTest`, `StandardizeNumericFeatures`, `SymmetricEigenDecomposition`, `WelchTTest` |
| [order_statistic.py](machine_learning/order_statistic.py) | `SelectOrderStatistic` |
| [pairwise_distances.py](machine_learning/pairwise_distances.py) | `PairwiseNumericDistances` |
| [parametric_curves.py](machine_learning/parametric_curves.py) | `EvaluateParametricCurve`, `FitParametricCurve` |
| [polynomial_roots.py](machine_learning/polynomial_roots.py) | `PolynomialRoots` |
| [randomization.py](machine_learning/randomization.py) | `PairedRandomizationTest` |
| [research_workflows.py](machine_learning/research_workflows.py) | `AdjustedRandAgreement`, `BinaryClassificationMetrics`, `ClusteringQualityMetrics`, `DecisionCostSummary`, `GroupTrainTestSplit`, `GroupedBootstrapMeanInterval`, `PCAReconstructionError`, `ProbabilityCalibrationSummary`, `ThresholdClassProbabilities`, `TimeSeriesSplitRecords` |
| [sign_assignments.py](machine_learning/sign_assignments.py) | `EnumerateSignAssignments` |
| [statistical_kernels.py](machine_learning/statistical_kernels.py) | Shared complete-family P-value correction and hypergeometric tail kernels. |
| [stratified_bootstrap.py](machine_learning/stratified_bootstrap.py) | `StratifiedClusterMeanInterval` |

## general

| 模块 | 公开工具／辅助职责 |
| --- | --- |
| [convex_geometry.py](general/convex_geometry.py) | `ConvexHalfspaceGeometry` |
| [csv_export.py](general/csv_export.py) | `SaveToCSVFile` |
| [data_tools.py](general/data_tools.py) | `ConvertRecordColumnTypes`, `FilterRecords`, `FormatMarkdownTable`, `GetJSONPointer`, `JoinRecordTables`, `ParseCSVRecords`, `ParseJSONDocument` |
| [file_records.py](general/file_records.py) | `QueryScientificRecordsFile` |
| [generalCommon.py](general/generalCommon.py) | `PaperQA`, `WolframAlpha` |
| [local_code_interpreter.py](general/local_code_interpreter.py) | `ExecuteNumericalCode` |
| [local_paperqa.py](general/local_paperqa.py) | Local PDF evidence retrieval and Qwen answers, sharing the Agent's inference worker. |
| [matrix_scaling.py](general/matrix_scaling.py) | `ScaleNumericMatrix` |
| [numeric_operations.py](general/numeric_operations.py) | `ElementwiseNumericOperations` |
| [numeric_slice.py](general/numeric_slice.py) | `SliceNumericArray` |
| [papers.py](general/papers.py) | `DownloadPapers` |
| [range_mask.py](general/range_mask.py) | `NumericRangeMask` |
| [record_inspection.py](general/record_inspection.py) | `ExtractNumericColumns`, `InspectScientificFile` |
| [research_data.py](general/research_data.py) | Read public structured source records without exposing private project files. |
| [research_workflows.py](general/research_workflows.py) | `AggregateRecordGroups`, `NormalizeNumericRows`, `SummarizeNumericTable` |
| [sequence_intervals.py](general/sequence_intervals.py) | `SelectSequenceIntervals` |
| [web_search_current.py](general/web_search_current.py) | `BingSearch` |

## shared

| 模块 | 公开工具／辅助职责 |
| --- | --- |
| [catalogue_price.py](shared/catalogue_price.py) | Read public mass-package catalogue prices from the supplier's CAS page. |
| [charge_density_metadata.py](shared/charge_density_metadata.py) | Read genuine legacy file/task metadata from official public CHGCAR object envelopes. |
| [chroma_weights.py](shared/chroma_weights.py) | Chroma's authorized weight download, with bounded requests and private credentials. |
| [common.py](shared/common.py) | 辅助实现；由上层模块导入。 |
| [data_validation.py](shared/data_validation.py) | Shared bounded JSON and finite numeric contracts for the local data tools. |
| [http_clients.py](shared/http_clients.py) | 辅助实现；由上层模块导入。 |
| [http_retry.py](shared/http_retry.py) | Bounded retry for public web services used by the biology tools. The shared project proxy and the public providers occasionally drop TLS connections or answer 429/5xx under load. E |
| [materials_api.py](shared/materials_api.py) | Bounded, authenticated requests and explicit molecule schema migration. |
| [pubchem.py](shared/pubchem.py) | Public PubChem queries with bounded retries and genuine, dated structure-response caches. |
| [qchem_details.py](shared/qchem_details.py) | Read real molecular detail fields from an explicitly supplied Q-Chem output. This adapter never assigns a fixture to an unrelated MP molecule identifier and does not run a quantum- |

