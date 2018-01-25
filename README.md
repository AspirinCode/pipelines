# Piplelines.

The project experiments with ways to generate data processing piplelines. 
The aim is to generate some re-usable building blocks that can be piped 
together into more functional pipelines. Their prime initial use is as executors
for the Squonk Computational Notebook (http://squonk.it) though it is expected
that they will have uses in other environments.

As well as being executable directly they can also be executed in Docker
containers (separately or as a single pipeline). Additionally they can be 
executed using Nextflow (http://nextflow.io) to allow running large jobs 
on HPC-like environments.

Currently it has some python scripts using RDKit (http://rdkit.org) to provide 
basic cheminformatics and comp chem functionality, though other tools will 
be coming soon, including some from the Java ecosystem.

* See [here](src/python/pipelines/rdkit/README.md) for more info on the RDKit components.
* See [here](src/nextflow/rdkit/README.md) for more info on running these in Nextflow.

Note: this is experimental, subject to change, and there are no guarantees that things work as expected!
That said, its already proved to be highly useful in the Squonk Computational Notebook, and if you are interested let us know, and join the fun.

The code is licensed under the Apache 2.0 license.

## Pipeline Utils

In Jan 2018 some of the core functionality from this repository was broken out into the [pipeline-utils](https://github.com/InformaticsMatters/pipeline-utils) repository. This included utility Python modules, as well as creation of a test framework that makes it easier to create and test new modules. This change also makes it easier to create additonal pipeline-like projects. See the [Readme](https://github.com/InformaticsMatters/pipelines-utils/blob/master/README.md) in the pipeline-utils repo for more details.

## General principles

### Modularity

Each component should be small but useful. Try to split complex tasks into 
reusable steps. Think how the same steps could be used in other workflows.
Allow parts of one component to be used in another component where appropriate
but avoid over use. For example see the use of functions in rdkit/conformers.py 
to generate conformers in o3dAlign.py 

### Consistency

Consistent approach to how components function, regarding:

1. Use as simple command line tools that can be piped together
1. Input and outputs either as files of using STDIN and STDOUT
1. Any info/logging written to STDERR to keep STDOUT free for output
1. Consistent approach to command line arguments across components

Generally use consistent coding styles e.g. PEP8 for Python.

## Input and output formats

We aim to provide consistent input and output formats to allow results to be 
passed between different implementations. Currently all implementations handle 
chemical structures so SD file would typically be used as the lowest common
denominator interchange format, but implementations should also try to support 
Squonk's JSON based Dataset formats, which potentially allow richer representations
and can be used to describe data other than chemical structures. 
The utils.py module provides helper methods to handle IO. 

### Thin output
 
In addition implementations are encouraged to support "thin" output formats
where this is appropriate. A "thin" representation is a minimal representation 
containing only what is new or changed, and can significantly reduce the bandwith
used and avoid the need for the consumer to interpret values it does not 
need to understand. It is not always appropriate to support thin format output 
(e.g. when the structure is changed by the process).

In the case of SDF thin format involves using an empty molecule for the molecule 
block and all properties that were present in the input or were generated by the 
process (the empty molecule is used so that the SDF syntax remains valid). 

In the case of Squonk JSON output the thin output would be of type BasicObject 
(e.g. containing no structure information) and include all properties that 
were present in the input or were generated by the process. 

Implicit in this is that some identifier (usually a SD file property, or 
the JSON UUID property) that is present in the input is included in the output so 
that the full results can be "reassembled" by the consumer of the output. 
The input would typically only contain additional information that is required 
for execution of the process e.g. the structure.

For consistency implementations should try to honor these command line 
switches relating to input and output:

-i and --input: For specifying the location of the single input. If not specified 
then STDIN should be used. File names ending with .gz should be interpreted as 
gzipped files. Input on STDIN should not be gzipped. 

-if and --informat: For specifying the input format where it cannot be inferred 
from the file name (e.g. when using STDIN). Values would be sdf or json.

-o and --output: For specifying the base name of the ouputs (there could be multiple
output files each using the same base name but with a different file extension.
If not specified then STDOUT should be used. Output file names ending with 
.gz should be compressed using gzip. Output on STDOUT would not be gzipped. 

-of and --outformat: For specifying the output format where it cannot be inferred 
from the file name (e.g. when using STDOUT). Values would be sdf or json.
 
--meta: Write additional metadata and metrics (mostly relevant to Squonk's 
JSON format - see below). Default is not to write.

--thin: Write output in thin format (only present where this makes sense).
Default is not to use thin format.

### UUIDs

The JSON format for input and oputput makes heavy use of UUIDs that uniquely 
identify each structure. Generally speaking, if the structure is not changed 
(e.g. properties are just being added to input structures) then the existing 
UUID should be retained so that UUIDs in the output match those from the input.
However if new structures are being generated (e.g. in reaction enumeration
or conformer generation) then new UUIDs MUST be generated as there is no longer
a straight relationship between the input and output structures. Instead you
probably want to store the UUID of the source structure(s) as a field(s) in 
the output. To allow correlation of the outputs to the inputs (e.g. for conformer
generation output the source molecule UUID as a field so that each conformer 
identifies which source molecule it was derived from.

When not using JSON format the need to handle UUIDs does not necessarily apply
(though if there is a field named 'uuid' in the input it will be respected accordingly). 
To accommodate this you are recommended to ALSO specify the input molecule number
(1 based index) as an output field independent of whether UUIDs are being handled
as a "poor man's" approach to correlating the outputs to the inputs.

### Filtering

When a service that filters molecules special attention is needed to ensure 
that the molecules are output in the same order as the input (obviously skipping
structures that are filtered out). Also the service descriptor (.dsd.json) file needs special care. For
instance take a look at the "thinDescriptors" section of src/pipelines/rdkit/screen.dsd.json

When using multi-threaded execution this is especially important as results 
will usually not come back in exactly the same order as the input.

### Metrics

To provide information about what happened you are strongly recommended to generate
a metrics output file (e.g. output_metrics.txt). This file allows to provide 
feedback about what happened. The contents of this file are fairly simple,
each line having a

`key=value`

syntax. Keys beginning and ending with __ (2 underscores) have magical meaning. 
All other keys are treated as metrics that are recorded against that execution.
The current magical values that are recognised are:

* InputCount: The total count of records (structures) that are processed
* OutputCount: The count of output records
* ErrorCount: The number of errors encountered

Here is a typical metrics file:

```
__InputCount__=360
__OutputCount__=22
PLI=360

```

It defines the input and output counts and specifies that 360 PLI 'units' 
should be recorded as being consumed during execution.

The purpose of the metrics is primarily to be able to chage for utilisation, but 
even if not charging (which is often the case) then it is still good practice
to record the utilisation.

### Metadata

Squonk's JSON format requires additional metadata to allow proper handling
of the JSON. Writing detailed metadata is optional, but recommended. If 
not present then Squonk will use a minimal representation of metadata, but 
it's recommended to provide this directly so that additional information can
be added. 

At the very minimum Squonk needs to know the type of dataset (e.g. MoleculeObject
or BasicObject), but this should be handled for you automatically if you use
the utils.default_open_output* methods. Better though to also specify metadata for
the field types when you do this. See e.g. conformers.py for an example of 
how to do this.

## Contact

Any questions contact: 

Tim Dudgeon
tdudgeon@informaticsmatters.com

Alan Christie
achristie@informaticsmatters.com
