#!/usr/bin/env python

# Copyright 2017 Informatics Matters Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse

from rdkit import Chem, rdBase
from rdkit.Chem import rdMolAlign

import conformers
from pipelines_utils import parameter_utils, utils
from pipelines_utils_rdkit import rdkit_utils

### start field name defintions #########################################

field_O3DAScore = "O3DAScore"

### start function defintions #########################################

def doO3Dalign(i, mol, qmol, threshold, perfect_score, writer, conformerProps=None, minEnergy=None):
    pyO3As = rdMolAlign.GetO3AForProbeConfs(mol, qmol)
    best_score = 0
    j = 0
    conf_id = -1
    for pyO3A in pyO3As:
        align = pyO3A.Align()
        score = pyO3A.Score()
        if score > best_score:
            best_score = score
            conf_id = j
        j +=1
        
    #utils.log("Best score = ",best_score)
    if not threshold or perfect_score - best_score < threshold:
        utils.log(i, align, score, Chem.MolToSmiles(mol, isomericSmiles=True))
        mol.SetDoubleProp(field_O3DAScore, score)
        if conformerProps and minEnergy:
            eAbs = conformerProps[conf_id][(conformers.field_EnergyAbs)]
            eDelta = eAbs -minEnergy 
            if eAbs:
                mol.SetDoubleProp(conformers.field_EnergyAbs, eAbs)
            if eDelta:
                mol.SetDoubleProp(conformers.field_EnergyDelta, eDelta)
        writer.write(mol, confId=conf_id)
        return 1
    return 0

### start main execution #########################################

def main():

    parser = argparse.ArgumentParser(description='Open3DAlign with RDKit')
    parser.add_argument('query', help='query molfile')
    parser.add_argument('--qmolidx', help="Query molecule index in SD file if not the first", type=int, default=1)
    parser.add_argument('-t', '--threshold', type=float, help='score cuttoff relative to alignment of query to itself')
    parser.add_argument('-n', '--num', default=0, type=int, help='number of conformers to generate, if None then input structures are assumed to already be 3D')
    parser.add_argument('-a', '--attempts', default=0, type=int, help='number of attempts to generate conformers')
    parser.add_argument('-r', '--rmsd', type=float, default=1.0, help='prune RMSD threshold for excluding conformers')
    parser.add_argument('-e', '--emin', type=int, default=0, help='energy minimisation iterations for generated confomers (default of 0 means none)')
    parameter_utils.add_default_io_args(parser)

    args = parser.parse_args()
    utils.log("o3dAlign Args: ", args)

    qmol = rdkit_utils.read_single_molecule(args.query, index=args.qmolidx)
    qmol = Chem.RemoveHs(qmol)
    qmol2 = Chem.Mol(qmol)

    source = "conformers.py"
    datasetMetaProps = {"source":source, "description": "Open3DAlign using RDKit " + rdBase.rdkitVersion}
    clsMappings = { "O3DAScore":   "java.lang.Float" }
    fieldMetaProps = [
        {"fieldName":"O3DAScore",   "values": {"source":source, "description":"Open3DAlign alignment score"}}
    ]
    if args.num > 0:
        # we generate the conformers so will add energy info
        clsMappings["EnergyDelta"] = "java.lang.Float"
        clsMappings["EnergyAbs"] = "java.lang.Float"
        fieldMetaProps.append({"fieldName":"EnergyDelta", "values": {"source":source, "description":"Energy difference to lowest energy conformer"}})
        fieldMetaProps.append({"fieldName":"EnergyAbs",   "values": {"source":source, "description":"Absolute energy"}})


    input,output,suppl,writer,output_base = rdkit_utils.\
        default_open_input_output(args.input, args.informat, args.output,
                                  'o3dAlign', args.outformat,
                                  valueClassMappings=clsMappings,
                                  datasetMetaProps=datasetMetaProps,
                                  fieldMetaProps=fieldMetaProps)

    pyO3A = rdMolAlign.GetO3A(qmol2, qmol)
    perfect_align = pyO3A.Align()
    perfect_score = pyO3A.Score()
    utils.log('Perfect score:', perfect_align, perfect_score, Chem.MolToSmiles(qmol, isomericSmiles=True), qmol.GetNumAtoms())

    i=0
    count = 0
    total = 0
    for mol in suppl:
        if mol is None: continue
        if args.num > 0:
            mol.RemoveAllConformers()
            conformerProps, minEnergy = conformers.process_mol_conformers(mol, i, args.num, args.attempts, args.rmsd, None, None, 0)
            mol = Chem.RemoveHs(mol)
            count += doO3Dalign(i, mol, qmol, args.threshold, perfect_score, writer, conformerProps=conformerProps, minEnergy=minEnergy)
        else:
            mol = Chem.RemoveHs(mol)
            count += doO3Dalign(i, mol, qmol, args.threshold, perfect_score, writer)
        i +=1
        total += mol.GetNumConformers()
    
    input.close()
    writer.flush()
    writer.close()
    output.close()

    if args.meta:
        utils.write_metrics(output_base, {'__InputCount__':i, '__OutputCount__':count, 'RDKitO3DAlign':total})

if __name__ == "__main__":
    main()

