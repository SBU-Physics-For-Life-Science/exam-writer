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

The input file is a YAML **list**.  Each item of the list starts with
`- ` and has one key that says what the item is: the exam's base name,
a block of LaTeX, the roster of students, a question, and so on.  The
items can appear in any order (except that a question is added to the
pool when it is read).  A complete, commented example is in
`samples/sample-test.yaml`.

A minimal exam looks like this:

```yaml
- Include: default-templates.yaml   # the LaTeX skeleton (always include it)
- Title: PHY121 Midterm Exam 2      # printed on the title page
- BaseName: phy121-midterm2         # output files are named after this

- Questions:                         # how many questions to draw from the pool
  - integrity:
      Choose: 999
      Choices: Academic.*
  - physics:
      Choose: 10
      Choices: Question.*

- Versions:                          # one exam copy per entry
    List:
      Fields: [LASTNAME, FIRSTNAME, SID]
      Values:
        - Extra, Exam, 000000000
    CSVFile:
      Fields: [LASTNAME, FIRSTNAME, SID]
      Name: ./roster.csv

- Constants:
    kGrav: "9.8"

- Question:
    Name: Question1.1
    Variables:
      M:
        Type: int
        Minimum: 1000
        Maximum: 2000
        Step: 10
    Text: |
      A &{M}~kg truck accelerates at 2~m/s$^2$.  What is the net force?
    Answers:
      A1:
        Correct: yes
        Text: $@[2t]{2*&{M}}$~N
      A2:
        Correct: no
        Text: $@[2t]{&{M}/2}$~N
    Solution: |
      $F = ma = @[2t]{2*&{M}}$~N.
```

### The blocks

| Key | Meaning |
|---|---|
| `Include: file.yaml` | Insert another YAML file here. `default-templates.yaml` holds the LaTeX skeleton and should always be included. The file is searched for in `.`, `./templates/` and `templates/` next to `exam-writer.py`. |
| `Title` | Exam title, available as `&{TITLE}` in the templates. |
| `BaseName` | Base of every output file name (see *Output files*). |
| `Questions` | Which questions to draw from the pool and how many (see *Choosing questions*). |
| `Versions` | Who gets an exam copy and what is printed on it (see *Versions*). |
| `Constants` | Named strings available everywhere as `&{name}`, the same on every copy. Usually physical constants. |
| `Variables` | Named values drawn at random once per exam copy, available everywhere. Same syntax as the variables of a question. |
| `Question` | One question added to the pool (see *Questions*). |
| `Preamble`, `FrontMatter`, `BackMatter`, `TitlePage`, `Prologue`, `Epilogue`, `QuestionBlock` | Blocks of LaTeX that override the defaults from `default-templates.yaml`. `Preamble` is the LaTeX header and must end with `\begin{document}`; `FrontMatter` comes after the title page and is the usual place for the constants table; `BackMatter` is scratch paper at the end. |

### Substitutions

Every block of text (question text, answers, solution, LaTeX blocks)
can contain:

| Syntax | Effect | Example |
|---|---|---|
| `&{name}` | Replaced by the value of a constant or variable. All `&{}` substitutions happen before any expression is evaluated, so a variable inside an expression is substituted as text. | `&{M}~kg` |
| `@{expression}` | The expression is evaluated by Python and the result inserted as is. | `@{2*&{N}}`, `@{"an" if &{L}==18 else "a"}` |
| `@[N]{expression}` | The expression is evaluated and rounded to `N` significant figures. | `@[3]{&{T}/&{R}}` |
| `@[Nt]{expression}` | Same, typeset for LaTeX: large or small results become `\ensuremath{1.2\times{}10^{3}}`. Use this inside or outside math mode. | `@[2t]{&{M}*&{kGrav}}` |
| `&&` | A literal `&`, needed in LaTeX tables. | `mass && 1.67~kg \\` |

Substitution is repeated until nothing changes, so a constant may use
another constant: `speedOfLight: '@[3t]{&{kLight}} \mps{}'` with
`kLight: "3E+8"` prints `3.00\times{}10^{8} \mps{}`.

The expression is Python, so `math.sqrt`, `math.sin`, `math.radians`,
`float()`, `max()` and so on are available.  **The expression can run
arbitrary Python code, so never use an input file from an untrusted
source.**  Because `@` is a reserved character in YAML, a value that
begins with `@` must be quoted, for example `Text: "@[2t]{&{V}}~m/s"`.

### Questions

```yaml
- Question:
    Name: Question1.4 #Problem 7.24     # unique; matched by Questions/Choices
    Points: 1                            # optional, default 1
    ExtraCredit: no                      # optional
    Before: all                          # optional ordering constraints:
    After: Question1.3                   #   all | a name | a list | a regex
    Follows: Question1.3                 # optional: always directly after that question
    Figure: figures/door.pdf             # optional PDF shown with the text
    Constants:                           # optional, local to this question
      m: "8000"
    Variables:                           # drawn again for every exam copy
      R:
        Type: float
        Minimum: 0.71
        Maximum: 1.00
        Step: 0.04
      N:
        Type: int
        Values: [2, 3, 4, 5]
    Unique:                              # optional: these strings must differ
      r: '&{R}'                          #   within one copy (redrawn otherwise)
    Text: |
      The handle is @[3t]{&{R}}~m from the hinge ...
    Answers:
      A1:
        Correct: yes
        Text: |
          @[2t]{&{T}/&{R}}~N
      A2:
        Correct: no
        Text: |
          @[2t]{2*&{T}/&{R}}~N
    Solution: |
      Torque balance gives ...
```

- `Name`, `Text` and `Answers` are required.  Everything else is optional.
- A variable is defined either by `Minimum`, `Maximum` and `Step`
  (a value `Minimum + k*Step` is drawn), or by `Values`, a list to pick
  from.  `Type: int` prints the value without a decimal point;
  `Type: float` prints it as Python does, so `&{R}` may print as
  `0.7999999999999999`: print float variables with `@[3t]{&{R}}` or add
  `Significant: 3` to the variable to round the drawn value itself.
- Answers are listed with any names (here `A1`..`A5`).  Their order in the
  file does not matter: the answers are shuffled on every copy, and the
  letter of the correct one goes to the key.  Keep the correct answer first
  only as a convention for readability.  An answer may also carry `Before`,
  `After` and `Follows` to fix its position, for example to keep "none of
  the above" last.
- Several answers may be `Correct: yes`.  The key then lists all their
  letters.
- The `Solution` is printed only in the key copy of the exam.

### Choosing questions

```yaml
- Questions:
  - anyLabel:
      Choose: 10            # how many to draw (999 = all that match)
      Choices: Question.*   # regular expression matched against question names
```

Each entry draws up to `Choose` questions whose name matches `Choices`,
in random order.  The labels and the order of the entries have no
meaning.  Use `Before`, `After` and `Follows` on the questions
themselves to control where a question lands.

### Versions

One exam copy is produced for every student in `Versions`.  Students
come from a `List` written in the file, from a `CSVFile`, or both.

```yaml
- Versions:
    List:
      Fields: [LASTNAME, FIRSTNAME, SID]
      Values:
        - Extra, Exam, 000000000          # a spare copy
    CSVFile:
      Fields: [LASTNAME, FIRSTNAME, SID]   # the columns of the CSV, in order
      Name: ./roster.csv
    Defaults:
      SECTION: L01                         # value for fields not in the file
```

- The field names become `&{LASTNAME}`, `&{FIRSTNAME}` and `&{SID}` in
  the templates and the columns of the key file.
- `Fields` must list the columns **in the order they appear in the CSV**,
  and the CSV must have **no header line**: every line is read as a
  student.  Use the same field order in `List` and `CSVFile`, because the
  key file's header is taken from the first copy.  A column to ignore
  can be named `DUMMY`.
- The CSV path is relative to the directory where `exam-writer.py` is
  run.

### Output files

For `BaseName: phy121-midterm2`, a run writes to the current directory:

| File | Content |
|---|---|
| `phy121-midterm2-0001.tex`, `-0002.tex`, ... | One LaTeX file per copy. `pdflatex file.tex` gives the student copy; `pdflatex "\def\printSolutions{}\input{file.tex}"` gives the key copy with the correct answers marked and the solutions. `build-exam.sh phy121-midterm2` does both for every copy. |
| `phy121-midterm2-keys.csv` | The answer key: one line per copy with the correct letter of every question, the question names in the order printed, and the student fields. This is the key file `exam-grader.py` reads. |
| `phy121-midterm2.log` | Everything the run printed, including the random seed and any warning or error. |
| `phy121-midterm2.pickle` | The generated exams, so they can be reprinted with `-P` after a template change without redrawing anything. |

### Checks made while generating

After every question is drawn, `exam-writer.py` checks it and reports
problems with the exam copy, the question number and name, the answer
names and the variable values, so the YAML can be corrected:

- **Repeated answers**: two options print the same text.  The question
  is drawn again with new variable values, up to ten times; after that
  the run stops.  Choose steps and distractors so values cannot
  coincide after rounding.
- **Floating point noise would be printed** (an error): a value such as
  `5.5600000000000005` would appear on the exam because a float variable
  is printed with `&{V}` instead of `@[3t]{&{V}}`.
- **Not enough digits** (an error): a variable is printed with fewer
  digits than it has, so the key uses digits the student cannot see.
- **Rounding midpoint** (a warning): the exact correct answer sits halfway
  between two printable values, for example `0.975` printed as `0.97`,
  so a student rounding by hand may pick the neighbouring option.  The
  number of such copies is printed at the end of the run; avoid them by
  changing the variable ranges or steps.

Use `-O` to build a single copy while writing an exam, and `-s SEED` to
reproduce an earlier run exactly.

[comment]: # Kludge a comment block with an empty line followed by lines
[comment]: # prefixed by '[comment]: #'

[comment]: # Local Variables:
[comment]: # mode:markdown
[comment]: # End:
