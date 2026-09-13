# Exam Writer

Generate multiple choice exams from YAML input files.  The exams can
have a randomized question order, randomized answer orders, and
randomized numbers in the exams.

## Running exam-writer.py

```
usage: exam-writer.py [-h] [-a] [-d] [-D] [-O] [-P] [-Y] [-s SEED] file

Write an exam based on YAML input files

positional arguments:
  file               An input file describing the exam

optional arguments:
  -h, --help         show this help message and exit
  -a, --all          Include all questions and do not reorder
  -d, --dry-run      Don't generate output files
  -D, --dump         Dump the input file to the output
  -O, --one-version  Build a single version (for debugging exam)
  -P, --pickle       Load existing exam version from a pickle file
  -Y, --yaml         Dump a YAML representation of the parsed input
  -s SEED, --seed SEED
                     Random seed to use, so the exam can be regenerated
                     identically later. Defaults to the current unix time.
```

Every run prints the seed it used to stderr (e.g. `Using random seed: 1234
(pass '-s 1234' to reproduce this run)`). Rerunning with `-s <seed>` picks
the same questions, the same question/answer order, and the same random
numbers as that earlier run — useful for regenerating an exam after a
wording or template fix without shuffling everything again.

## The input YAML file

There is a sample exam in `samples/sample-test.yaml` which has been used
for testing the `exam-writer.py` script.  The YAML file needs to be written
for the pyYAML input parser, with one minor extension.  When the file is
read, and before it is parsed, lines with the format:

```
- Include: <filename.yaml>
```

are interpreted to name an include file, which is included into the input
stream of the pyYAML parser.  The file name is search for along the path
```.:./templates/:${SCRIPTDIR}/templates/``` where ```SCRIPTDIR``` is the
directory containing `exam-writer.py`.  The filename can be anything, but
it is recommended to use "yaml" as an extension.



[comment]: # Kludge a comment block with an empty line followed by lines
[comment]: # prefixed by '[comment]: #'

[comment]: # Local Variables:
[comment]: # mode:markdown
[comment]: # End:
