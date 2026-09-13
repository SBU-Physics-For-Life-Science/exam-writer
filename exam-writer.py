#!/usr/bin/env python3

import yaml
import csv
import string
import textwrap
from graphlib import TopologicalSorter
import argparse
import random
import os.path
import re
import sys
import json
import pickle
import math
import io
import time

parser = argparse.ArgumentParser(
    description="Write an exam based on YAML input files")
parser.add_argument("file",nargs=1,
                    help="An input file describing the exam")
parser.add_argument('-a','--all', dest='allQuestions', default=False,
                    action='store_true',
                    help="Include all questions and do not reorder")
parser.add_argument('-d','--dry-run', dest='dryRun', default=False,
                    action='store_true',
                    help="Don't generate output files")
parser.add_argument('-D','--dump', dest='dumpInput', default=False,
                    action='store_true',
                    help="Dump the input file to the output")
parser.add_argument('-O','--one-version', dest='oneVersion', default=False,
                    action='store_true',
                    help="Build a single version (for debugging exam)")
parser.add_argument('-P','--pickle', dest='pickle', default=False,
                    action='store_true',
                    help="Load existing exam version from a pickle file")
parser.add_argument('-Y','--yaml', dest='dumpYAML', default=False,
                    action='store_true',
                    help="Dump a YAML representation of the parsed input")
parser.add_argument('-s','--seed', dest='seed', default=None, type=int,
                    help="Random seed to use, so the exam can be regenerated "
                    "identically later. Defaults to the current unix time.")
options = parser.parse_args()

## Seed the random module so a run can be reproduced later.  If no seed was
# given on the command line, derive one from the current time and report it,
# so it can be passed back in with `-s` to reproduce this exact run.
seed = options.seed if options.seed is not None else int(time.time())
random.seed(seed)
print(f"Using random seed: {seed} (pass '-s {seed}' to reproduce this run)",
      file=sys.stderr)

###################################################################
# The Value class hierarchy: These are for holding values that will be
# used in the exam.  They are used to implement constants, global
# variables, random variables (both for a list of values and a value
# in a range.
###################################################################

## An object containing one particular instance of a value.
#
# An instance of an object will have one possible value of the object
# and will not change.  This is what will eventually be substituted
# into the exam.  The ValueInstance objects are returned by the
# `Value.get()` method.  The value of the instance is generated when
# it is constructed and not changed.
class ValueInstance(object):
    def __init__(self,value):
        self.value = value
        self.instance = value.update()

    def __str__(self): return self.get()

    def name(self) -> str: return self.value.name()

    def get(self) -> str : return self.instance

## An object containing a named value.
#
# This provides the base class for several other value related classes
# and implements the external interface.
class Value(object):
    """An object containing a named string value."""

    ## Construct a Value object `Value('name')`
    #
    # A Value object with `name` is constructed with an intial
    # value of 'not-set'.
    def __init__(self, name: str):
        self.type = "str"
        self.valueName = name

    ## Return the name of the object.
    def name(self) -> str:
        return self.valueName

    ## Get an instance of the object.
    def get(self): return ValueInstance(self)

    ## Set the name of the object.
    #
    # Be careful using this since the object is often in a dictionary
    # where it is assumed that the object name will match the key
    # name.
    def setName(self, name: str) -> None:
        self.valueName = name

    ## Update the value of the object
    #
    # This is a "no-op" for the base class.  For derived classes this
    # may update the value.  Example: RandomRangeValue.
    def update(self) -> str:
        return "not-set"

## An object containing a constant string value.
#
class ConstantValue(Value):

    ## Construct the object.
    #
    # This requires the `name` of the object and a string value
    # `v`.  The value cannot be changed after it is constructed.
    def __init__(self, name: str, v: str):
        super().__init__(name)
        self.value = v

    def update(self) -> str: return self.value

## An object that chooses a random element of a list and returns as a string
#
# When update is called, this will choose a new element of the value list.
class RandomListValue(Value):
    ## Construct a RandomListValue object
    #
    # This constructs a RandomeListValue object with `name`, and a
    # dictionary `inputs`.  The dictionary must contain the keys
    #
    # - Significant: [int, optional] The number of significant figures
    #
    # - Values: [list, required] A list of values that will be chosen
    #   by update. For example, inputs can have a value of `{"Values":
    #   ["one", "two", "three"]}`
    #
    # - Type: [str|float, optional] If the value is a number, how
    #   should it be converted into a string. [x
    def __init__(self, name: str, inputs: dict):
        super().__init__(name)
        if "Values" not in inputs: raise ValueError("Must include Values")
        v = inputs["Values"]
        if not type(v) is list: raise ValueError("Must be a list")
        self.values = v
        if "Type" in inputs: self.type = inputs["Type"]
        self.significant = None
        if "Significant" in inputs: self.significant=str(inputs["Significant"])


    ## Not a valid operation on this class
    def set(self, v : str) -> None:
        raise RuntimeError("Cannot set a RandomListValue")

    ## Update the value with a new choice from the list of values.
    #
    # The value in the list will be converted to a string using `str()`.
    def update(self) -> str:
        # Generate a new value.
        v = random.choice(self.values)
        if self.type == "int": v = int(v)
        if self.type == "float": v = float(v)
        if self.significant is not None:
            v = SignificantFigures(v,str(self.significant)+"g")

        return str(v);

## An object that chooses a value inside a range.
#
# When `update()` is called, this will generate a new value inside the
# range.
class RandomRangeValue(Value):

    ## Construct a RandomRangeValue object
    #
    # This constructs a `RandomRangeValue` object with `name`, and a
    # dictionary `inputs`.  The dictionary must contain the keys
    #
    # - Significant: [int, optional] The number of significant figures
    #
    # - Minimum : [float, required] The minimum value of the range
    #
    # - Maximum : [float, required] The maximum value of the range
    #
    # - Step : [float, required] The step between choses values in the
    #   range
    #
    # - Type : [int|float] How to translate the numeric value into a
    #   string
    #
    def __init__(self, name: str, inputs: dict):
        super().__init__(name)
        if "Minimum" not in inputs: raise ValueError("Must include Minimum")
        self.minimum = float(inputs["Minimum"])
        if "Maximum" not in inputs: raise ValueError("Must include Maximum")
        self.maximum = float(inputs["Maximum"])
        if "Step" not in inputs: raise ValueError("Must include Step")
        self.step = float(inputs["Step"])
        if "Type" in inputs: self.type = inputs["Type"]
        self.significant = None
        if "Significant" in inputs: self.significant=str(inputs["Significant"])

    ## Not a valid operation for this class
    def set(self, v : str) -> None:
        raise RuntimeError("Cannot set a RandomRangeValue")

    ## Choose a new value from the range.
    def update(self) -> str:
        i = int((self.maximum-self.minimum)/self.step+1E-6)
        if i<0: i = 0
        v = self.minimum + self.step*random.randint(0,i)
        if self.type == "int": v = int(v)
        if self.type == "float": v = float(v)
        if self.significant is not None:
            v = SignificantFigures(v,str(self.significant)+"g")
        return str(v);

## Build a dictionary of ConstantValue objects
#
# Take an input dictionary of constant names and values and return a
# dictionary that can be used to update a dictionary of constant
# definitions.  The dictionary should have entries with the key being
# the constant name and the value being a string associated with the
# name.
def MakeConsts(d : dict) -> dict:
    out = dict()
    for key in d:
        val = d[key]
        if not type(val) is str:
            print("The value for",key,"must be a string:", val)
            raise ValueError("Constants must be strings")
        out[key] = ConstantValue(key,val)
    return out

## Build a dictionary of RandomRangeValue and RandomListValue objects
#
# Take an input dictionary of names and values and return a dictionary
# that can be used to update a dictionary of variable definitions.
# The dictionary should have entries with the key being the name and
# the a dictionary to build either a RandomRangeValue or a
# RandomListValue object.
def MakeValues(d : dict) -> dict:
    out = dict()
    for key in d:
        val = d[key]
        if type(val) is str: out[key] = Value(key,val)
        elif "Values" in val: out[key] = RandomListValue(key,val)
        else: out[key] = RandomRangeValue(key,val)
    return out

## A class to hold an Answer.
#
# This is one multiple choice answer that will be added to a question.
# The answer is described by a `name` and a dictionary.  The `name` is
# arbitrary, but should be unique within a question, and is used to
# reference the answer inside of the question description.  The order
# of answers may be randomized for the exam.  The input dictionary
# describes the answer and has the following keys.
#
# - Correct : [yes|no, required] Is this a correct answer to the
#   question.
#
# - Text : [str, required] A template for the LaTeX that will be used
#   to build the answer.  Strings with the format &{name} will be
#   substituted with the answer is build.  In addition to Value
#   objects defined for the question and exam, the names are available
#
# - Before : ["all"|name|regex|list, optional] A selection of answer
#   names that this answer must be before ("all" means this is the
#   first answer).
#
# - After : ["all"|name|regex|list, optional] a selection of answer
#   names that htis answer must be after ("all" means that this is the
#   last answer).
#
# - Follows: [name, optional] A name of a answer that this must
#   follow.  This answer will come immediately after the named answer.
#
class Answer(object):
    def __init__(self, name: str, d: dict):
        self.configuration = d
        self.name = name
        self.before = None
        self.after = None
        self.follows = None

        # Check for required keys
        if "Correct" not in d: raise ValueError("Must be have Correct field")
        if "Text" not in d: raise ValueError("Answer must have text")
        for k in d:
            if "Text" == k:  self.text = d[k]
            elif "Correct" == k: self.correct = d[k]
            elif "Before" == k: self.before = d[k]
            elif "After" == k: self.after = d[k]
            elif "Follows" == k: self.follows = d[k]
            else:
                print("Bad key",k,"in",d)
                raise ValueError("Unknown key in question")

## Build a dictionary of Answer objects.
#
# This produces a dictionary with a key being the answer name, and the
# value is the associated Answer object.  The input dictionary should
# have keys that are the answer names, and a dictionary as described
# for the Answer object.
def MakeAnswers(d : dict) -> dict:
    out = dict()
    for key in d:
        val = d[key]
        if not type(val) is dict:
            print("The value for",key,"must be a dictionary")
            raise ValueError("Answers must be dictionaries")
        out[key] = Answer(key,val)
    return out

## An object describing one question.
#
# This is one multiple choice question that will be added to the exam.
# The question is constructed using a dictionary.  The
# order of the questions may be randomized for the exam.  The input
# dictionary describes the question and has the following keys:
#
# - Name : [str, required] The `name` is arbitrary, but should be
#   unique within the exam.  It is used to reference the question
#   inside the exam description.
#
# - Points : [int, optional] The number of points for this question.
#   The value can be referenced inside the question template using
#   "&{POINTS}".
#
# - Index : [int, optional] The ordering for this question.  This only
#   has meaning with the question order is not randomized.
#
# - Before : ["all"|name|regex|list, optional] A selection of question
#   names that this question must be before ("all" means this is the
#   first question).
#
# - After : ["all"|name|regex|list, optional] a selection of question
#   names that this question must be after ("all" means that this is the
#   last question).
#
# - Follows : [name, optional] A name of a question that this must
#   follow.  This question will come immediately after the named
#   questions.  This is used to construct follow up questions.
#
# - Constants : [dict, optional] A dictionary that can be handed to
#   `MakeConsts`
#
# - Variables : [dict, optional] A dictionary that can be handed to
#   `MakeValues()`
#
# - Unique : [dict, optional] A dictionary that can be handed to
#   `MakeConsts()`, but which has a special set of symantics.  The
#   constants should be strings with &{name} and @{name} values.  When
#   a question instance is generated these will be filled based on the
#   variables and constants, and the checked that they are unique.  If
#   the values are not unique, they variables will be updated, and the
#   values checked again (if a unique set can't be found, it will
#   eventually give up and raise an error)
#
# - Answers : [dict, required] A dictionary of answers to the
#   question.  See the Answers class for details.
#
# - Text : [str, required] A template for the LaTeX that will be used
#   to build the question.  Strings with the format &{name} will be
#   substituted with the question is build.  In addition to Value
#   objects defined for the question and exam.
#
# - Solution : [str, optional] A template for the LaTeX used to print
#   the solution.
#
# - Figure : [str, optional] A pdf file name for a figure that will be
#   included with the question.
#
class Question(object):
    def __init__(self, d: dict):
        self.configuration = d
        self.name = "not-set"
        self.points = 1
        self.extraCredit = False
        self.index = None
        self.before = None
        self.after = None
        self.follows = None
        self.constants = dict()
        self.variables = dict()
        self.unique = dict()
        self.answers = dict()
        self.text = "not-set"
        self.figure = None
        self.soln = "There is no solution."

        # Check for required keys
        if "Name" not in d: raise ValueError("Question must have name")
        if "Text" not in d: raise ValueError("Question must have text")
        if "Answers" not in d: raise ValueError("Question must have answers")
        for k in d:
            if "Name" == k: self.name = d[k]
            elif "Points" == k: self.points = d[k]
            elif "ExtraCredit" == k: self.extraCredit = d[k]
            elif "Index" == k: self.index = int(d[k])
            elif "Before" == k: self.before = d[k]
            elif "After" == k: self.after = d[k]
            elif "Follows" == k: self.follows = d[k]
            elif "Constants" == k: self.constants = MakeConsts(d[k])
            elif "Variables" == k: self.variables = MakeValues(d[k])
            elif "Unique" == k: self.unique = MakeConsts(d[k])
            elif "Answers" == k: self.answers = MakeAnswers(d[k])
            elif "Figure" == k: self.figure = d[k]
            elif "Text" == k:  self.text = d[k]
            elif "Solution" == k: self.soln = d[k]
            else:
                print("Bad key",k,"in",d)
                raise ValueError("Unknown key in question")

        self.constants["NAME"] = ConstantValue("NAME",str(self.name))
        self.constants["POINTS"] = ConstantValue("POINTS",str(self.points))
        self.constants["TEXT"] = ConstantValue("TEXT",self.text)
        if self.figure:
            self.constants["FIGURE"] = ConstantValue("FIGURE",self.figure)
        self.constants["SOLUTION"] = ConstantValue("SOLUTION",self.soln)


## Hold the description of how to choose the questions
#
# This produces a list with pairs (two element tuples).  The first
# element of the tuple is name of the question sequence being
# described, the second element is a dictionary with the keys "Choose"
# which sets the number of questisons of this type to be choses, and
# the second element is a "selection" of which questions to choose.
class Questions(object):
    def __init__(self, d : dict):
        self.sequence = list()
        for s in d:
            if len(s) != 1:
                raise ValueError("Invalid question group")
            group = s.popitem()
            self.sequence.append(group)

## Hold the version specific fields.
#
# These can be read for a CSV file, or specified in the YAML file as
# lists.  This is used to fill constant names that are changed for
# each version of the exam.  The most common names are "LASTNAME",
# "FIRSTNAME", and "SID" (student id), but the actual names are
# specified in the YAML file describing the exam.
class Versions(object):
    # Construct a Versions object
    #
    # This takes a dictionary describing the versions.  The keys are
    #
    # - Defaults : A dictionary of default names (as the key) and
    #   values.
    #
    # - List : Specifies a the fields and a list of "rows" to be used.
    #   This is a dictionary with the keys
    #
    #   + Fields : A list of field names.  If a field name contains a
    #     substring string "DUMMY", the field will not be processed.
    #
    #   + Values : A list of strings used to fill the fields.  Each
    #     string is a different version of the exam, and should
    #     containe a comma separated list of field values
    #
    # - CSVFile : a dictionary with the keys
    #
    #   + Name : the CSV file name.
    #
    #   + Fields : A list of the field names inside the CSV file.  If
    #     a field name contains a substring string "DUMMY", the field
    #     will not be processed.
    #
    def __init__(self, d):
        # A list of dictionaries that are used for substitutions in the exam
        self.inputs = list()
        # A dictionary used to initialize a particular version dictionary.
        self.defaults = dict()
        if "List" in d: self.HandleList(d["List"])
        if "CSVFile" in d: self.HandleCSV(d["CSVFile"])
        if "Defaults" in d: self.defaults = d["Defaults"]

    ## Implement parsing the List of versions from the YAML file
    def HandleList(self, d):
        fields = d["Fields"]
        for line in d["Values"]:
            vers = dict()
            values = [v.strip() for v in line.split(",")]
            for k, v in zip(fields,values):
                # REJECT dummy fields
                if 'DUMMY' in k: continue
                if 'Dummy' in k: continue
                if 'dummy' in k: continue
                vers[k] = v
            for k in self.defaults:
                if k not in vers: vers[k] = self.defaults[k]
            self.inputs.append(vers)

    ## Implement reading the versions from a CSV file
    def HandleCSV(self, d):
        fields = d["Fields"]
        file = d["Name"]
        try:
            with io.open(file,"r",encoding="ascii",errors="ignore") as f:
                reader = csv.DictReader(f,fieldnames=fields)
                for v in reader:
                    vers = dict()
                    for k in fields:
                        # REJECT dummy fields
                        if 'DUMMY' in k: continue
                        if 'Dummy' in k: continue
                        if 'dummy' in k: continue
                        vers[k] = v[k]
                    for k in self.defaults:
                        if k not in vers: vers[k] = self.defaults[k]
                    self.inputs.append(vers)
        except:
            print("VERSIONS CSV FILE IS MISSING: ", file)
            pass


## Hold a description of the exam.
#
# This is filled by parsing the top level of the YAML file.  It
# accepts the name of the YAML file to read.  After the yaml file has
# been read the elements are checked, and then used to fill the fields
# of this object.
class Exam(object):
    def __init__(self, name: str):
        self.configuration = self.loadConfiguration(name)
        self.pool = dict()
        self.templates = dict()
        self.constants = dict()
        self.variables = dict()
        for  block in self.configuration: self.topLevel(block)

    def topLevel(self, d):
        if not type(d) is dict:
            raise TypeError("Blocks must be dictionaries")

        if "Title" in d: self.title = d["Title"]
        elif "BaseName" in d: self.baseName = d["BaseName"]
        elif "Constants" in d:
            vals = MakeConsts(d["Constants"])
            for key in vals:
                if key in self.constants:
                    raise ValueError("Duplicate constant value: " + key)
                else:
                    self.constants[key] = vals[key]
        elif "Variables" in d:
            vals = MakeValues(d["Variables"])
            for key in vals:
                if key in self.variables:
                    raise ValueError("Duplicate global variable: " + key)
                else:
                    self.variables[key] = vals[key]
        elif "Questions" in d: self.questions = Questions(d["Questions"])
        elif "Versions" in d: self.versions = Versions(d["Versions"])
        elif "Question" in d: self.buildQuestion(d["Question"])
        elif "QuestionTemplate" in d:
            self.questionTemplate = d["QuestionTemplate"]
        elif "QuestionWithFigureTemplate" in d:
            self.questionWithFigureTemplate = d["QuestionWithFigureTemplate"]
        elif "AnswerTemplate" in d: self.answerTemplate = d["AnswerTemplate"]

        elif "ExamTemplate" in d: self.examTemplate = d["ExamTemplate"]
        elif "Prologue" in d: self.templates["PROLOGUE"] = d["Prologue"]
        elif "Preamble" in d: self.templates["PREAMBLE"] = d["Preamble"]
        elif "TitlePage" in d: self.templates["TITLEPAGE"] = d["TitlePage"]
        elif "FrontMatter" in d:
            self.templates["FRONTMATTER"] = d["FrontMatter"]
        elif "QuestionBlock" in d:
            self.templates["QUESTIONBLOCK"] = d["QuestionBlock"]
        elif "BackMatter" in d: self.templates["BACKMATTER"] = d["BackMatter"]
        elif "Epilogue" in d: self.templates["EPILOGUE"] = d["Epilogue"]

        else:
            print(d)
            raise ValueError("Unknown key in exam file")

    def buildQuestion(self, q : dict):
        """Add a question to the pool"""
        if "Name" not in q: raise ValueError("Missing question name")
        name = q["Name"]
        self.pool[name] = Question(q)

    def readFile(self,name: str) -> str:
        """Read the contents of a file and return it as a string.

        The file "name" is read.  Any include files are included and
        the total result is returned as a string.

        """

        print("Looking for input file: ", name)

        # Find the real name of the input file.  This searchs in a very
        # limited path.
        realName = ""
        # Check in the current working directory
        if os.path.isfile(name):
            realName = name
        # Check in the config subdirectory of the current working directory
        elif os.path.isfile("./templates/"+name):
            realName = "./templates/" + name
        # Check in the config subdirectory of the script location.
        elif os.path.isfile(os.path.dirname(__file__)+"/templates/"+name):
            realName = os.path.dirname(__file__)+"/templates/"+name
        # Give up!
        else:
            raise ValueError("File not found")

        config  = "###############################################\n"
        config += "# Including: " + realName + "\n"
        config += "###############################################\n"

        with open(realName,'r') as f:
            for line in f:
                if line.lstrip()[0:10] == "- Include:":
                    config += self.readFile(line.split()[2])
                    continue
                config += line

        config += "###############################################\n"
        config += "# End of: " + realName + "\n"
        config += "###############################################\n"

        return config

    def loadConfiguration(self,name: str):
        """Read the contents of a file and return as a list"""
        config = self.readFile(name)
        if options.dumpInput: print(config)
        input = yaml.safe_load(config)
        if options.dumpYAML: print(yaml.dump(input))
        return input

################################################################
#
# Expand variables and expressions in a string.
#
################################################################

## Expand all of the variable and mathematical expressions
#
# This takes an `input` string and a dictionary, `d`, and expands all
# of the values and mathematical expressions.  The dictionary should
# contain keys for all of the variables that are being replaced.
# Instances of &{name} are replaced inside the input string using the
# dictionary.  After all of the named variables are replaced, all
# instances of @{expr}, and @[sigfig]{expr} are expanded.
#
# Templates to be replace:
#
# - &{name} : Looks up `name` in the input dictionary and replaces
#         using that value.  For example if the dictionary contains
#         `{"spelling" : "yellow"}` an input string of "a &{spelling}
#         bee"  becomes "a yellow bee".
#
# - @{expr} : Applys eval to the expression (after all variables have
#         been expanded.  For instance, "@{1+1}" becomes "2"
#
# - @[sigfig]{expr} : After the expression has been evaluated, it is
#         rounded to the number of significant figures.  For instance,
#         "@[3]{1+1}" becomes "2.00".
#
# - @[sigfig(t|T)[expr] : Evaluate the expression and round the the
#         requested significant figures, then translate into a LaTeX
#         expression for the number in scientific notation.  For
#         example, "@[2t]{3E+8}" is "\ensuremath{3.0\times{}10^{8}}"
#
def ExpandString(input: str, d: dict) -> str:
    if not type(input) is str: raise TypeError("Can only expand a string")

    # A sub-class to override the default behavior of string.Template
    class Expand(string.Template): delimiter='&'

    # Iteratively substitute strings until the value stops changing
    value = str(input)
    result = ""
    while result != value:
        result = value
        value = Expand(value).safe_substitute(d)

    # Expand all of the expressions
    value = result
    result = ""
    while result != value:
        result = value
        value = ExpandExpression(value)

    return result

## Expand all of the mathematical expressions in a string.
#
# See the ExpandString documentation for more details.
def ExpandExpression(input: str) -> str:
    parse = re.search(r"@(\[([0-9tT]*)\]){0,1}\{([^{}]*)\}",input)
    if parse == None: return input
    sigfig = parse[2]
    if sigfig != None and len(sigfig) < 1: sigfig = None
    # Next expression strips all whitespace
    # expr_string = parse[3].translate(str.maketrans('','',string.whitespace))
    # Next expression strips new lines.
    expr_string = parse[3].translate(str.maketrans('','','\n\r'))
    try:
        expr = eval(expr_string)
    except:
        print("Expression error in:", expr_string)
        print("Parse:", parse)
        raise RuntimeError("Parse error")
    expr = SignificantFigures(expr,sigfig)
    result = input[:parse.span()[0]] + expr + input[parse.span()[1]:]
    return result

## Apply the significant figure rounding to the input value
#
# If the string `sigfig` contains T or t, the number is translated
# into a form suitable for LaTeX.
def SignificantFigures(input,sigfig) -> str:
    latex = False
    general = False
    if sigfig == None: sigfig = ""
    if "g" in str(sigfig):
        general = True
        sigfig = sigfig.replace("g","")
    if "G" in str(sigfig):
        general = True
        sigfig = sigfig.replace("G","")
    if "t" in str(sigfig):
        latex = True
        sigfig = sigfig.replace("t","")
    if "T" in str(sigfig):
        latex = True
        sigfig = sigfig.replace("t","")
    if len(sigfig) < 1: value = str(input)
    else: value = ("{:#." + str(int(sigfig)) + "g}").format(input)
    if general: value = ("{:g}").format(float(value))
    if not latex: return value.rstrip(".")
    # Turn the value into a LaTeX number
    mantSign = ""
    if value[0] == '-':
        mantSign = "-"
        value = value[1:]
    parse = re.search("([0-9.]*)[Ee]([+-])([0-9]*)",value)
    if not parse:
        value = value.rstrip(".")
        return mantSign+value
    mant = parse.group(1).rstrip(".")
    sign = parse.group(2)
    if sign == "+": sign = ""
    expo = parse.group(3).lstrip("0")
    value  = "\\ensuremath{" + mantSign +  mant +"\\times{}10^{" + sign + expo +"}}"
    return value

################################################################
# Build a list of keys from an input dictionary based on a selection
# criteria.  The ordering must be "Before", or "After", The input
# selection will have a value of
#   "all" -- means that everything in the input dictionary is selected
#            Except it needs to exclude the current element if the element
#            is in the dictionary.  It's also an error if "all" happens
#            more than once.  It also excludes any element that has a
#            "Follows" key.
#   "aName" -- a string interpreted as a regular expression
#   ["name1", "name2, ...] -- a list of regular expressions
################################################################
def BuildSelection(selection, d: dict) -> list:
    if selection is None: return list
    if selection == "all": return SelectAll(d)
    if type(selection) is str: return SelectName(selection,d)
    if type(selection) is list: return SelectList(selection,d)
    raise ValueError("Selection is not valid")

def SelectAll(selection, d: dict) -> list:
    out = []
    for k in d:
        if d[k].follows is not None: continue
        out.append(k)
    return out

def SelectName(selection, d: dict) -> list:
    out = []
    for k in d:
        if d[k].follows is not None: continue
        if re.fullmatch(selection,k) != None: out.append(k)
    return out

def SelectList(selection, d: dict) -> list:
    out = []
    for name in names:
        out += SelectName(name, d)

## Build a list of key names matching the selection
#
# This selects all of the keys in a dictionary that match a selection
# criteria.  The selection criteria can be None, string, or a list
# of strings.
#
# - selection -- This is a selection criteria that will be applied
#                     to the dictionary.  The possible values are
#
#   + None  : No keys are selected
#
#   + "all" : Select all keys in the dictionary, except keys which
#                         contain "all" in the "after" field
#
#   + "name" : A regular expression (usually this is just a name).
#                        This selects all of the keys matching the
#                        regular expression, except keys containing
#                        "all" in the "before" field
#
#   + list   : A list of regular expressions following the
#                        same rules as "name"
#
# -d -- A dictionary.  The elements of the dictionary should also be
#                     dictionaries, and may contain the "before" and
#                     "after" fields.
#
# Return Value: A list of dictionary keys that match the selection
#         criteria.
def BuildBefore(selection, d: dict) -> list:
    if selection is None: return list()
    if selection == "all": return BuildBeforeAll(d)
    if type(selection) is str: return BuildBeforeRegEx(selection,d)
    if type(selection) is list: return BuildBeforeList(selection,d)
    raise ValueError("Selection is not valid")

# Build a list of all keys except those that have entries with: "all"
# in the before field; or, have a "follows" field.
def BuildBeforeAll(d: dict) -> list:
    out = []
    allCount = 0   # More than one "all" is OK, maybe(!)
    for k in d:
        if d[k].before is not None and d[k].before == "all":
            allCount += 1
            continue
        if d[k].follows is not None: continue
        out.append(k)
    return out

# Build a list of keys that match the name (a regular expression
# string).  This will not contain keys for items with "all" in the
# before field, or which contain a "follows" field
def BuildBeforeRegEx(name: str, d: dict) -> list:
    out = []
    for k in d:
        if d[k].before is not None and d[k].before == "all": continue
        if d[k].follows is not None: continue
        if re.fullmatch(name,k) != None: out.append(k)
    return out

# Apply BuildBeforeRegEx to a list of strings.
def BuildBeforeList(names: list, d: dict) -> list:
    out = []
    for name in names:
        out += BuildBeforeRegEx(name, d)
    return out

## Build a list of keys matching the selection
#
#    Arguments:
#        selection -- This is a selection criteria that will be applied
#                     to the dictionary.  The possible values are
#                 None  : No keys are selected
#                 "all" : Select all keys in the dictionary, except
#                         keys which contain "all" in the "After" field
#                 "name" : A regular expression for a single name
#                        (usually this is just a constant string)
#                 list   : A list of regular expressions following the
#                        same rules as "name"
#        d -- A dictionary.  The elements of the dictionary should also
#                     be dictionaries, and may contain the "After"
#                     field.
#
#    Return Value: A list of dictionary keys that match the selection
#         criteria.
def BuildAfter(selection, d: dict) -> list:
    if selection is None: return list()
    if selection == "all": return BuildAfterAll(d)
    if type(selection) is str: return BuildAfterRegEx(selection,d)
    if type(selection) is list: return BuildAfterList(selection,d)
    raise ValueError("Selection is not valid")

def BuildAfterAll(d: dict) -> list:
    out = []
    allCount = 0   # More than one "all" is OK, maybe(!)
    for k in d:
        if d[k].after == "all":
            allCount += 1
            continue
        if d[k].follows != None: continue
        out.append(k)
    return out

def BuildAfterRegEx(name: str, d: dict) -> list:
    out = []
    for k in d:
        if d[k].after == "all": continue
        if d[k].follows != None: continue
        if re.fullmatch(name,k) != None: out.append(k)
    return out

def BuildAfterList(names: list, d: dict) -> list:
    out = []
    for name in names:
        out += BuildAfterRegEx(name, d)
    return out

## Choose a list of object from a pool of Question or Answer objects.
#
# This builds a list of up to `count` objects from the `pool` based on
# the `selection`.  If the pool has fewer than `count` objects, then
# all of them will be used.  The `pool` must be a dictionary of
# objects with `name` and `follows` fields.  Any question that follows
# a chosen question is also chosen.
#
# The `ChooseFromPool()` function makes sure that when an object
# (i.e. a Question or Answer) is chosen, any follow questions are also
# chosen.  This causes a minor "feature" at the very end of list of
# chosen objects since the object cannot have a follow-up since that
# would make the list too long.  If adding a follow up will make the
# list to long, the object and its follow-up(s) are skipped.
def ChooseFromPool(pool, selection, count = 999):
    # Find all the questions in the pool that are suppose to follow
    # another question.
    follows = dict()
    for k in pool:
        if pool[k].follows != None: follows[pool[k].follows] = pool[k]
    # Find all the questions in the pool that match the selection and
    # shuffle the order.
    choices = BuildSelection(selection,pool)
    if not options.allQuestions: random.shuffle(choices)
    # Add questions to the output starting from the first chosen question
    out = []
    for choice in choices:
        # See if the current choice will fit into the output
        trial = [choice]
        # Add any questions that must follow the choice to the trial
        while trial[-1] in follows: trial.append(follows[trial[-1]].name)
        # Make sure the trial doesn't make the output too long.  If
        # the output would be to long, then skip the choice.
        if len(out) + len(trial) > count: continue
        # The length is OK, so add the trial to the output
        out += trial
        if len(out) >= count: break
    return out

## Order the values in the chosen list.
#
# This applies the "Before", "After", and "Follows" constraints to the
# chosen list.  NOTE: This only looks in the input list, so if there
# is a question that should follow another, but it is not in the input
# list, it still won't be in the output list.
def OrderChosen(input, pool):
    chosen = input
    if not options.allQuestions: random.shuffle(chosen)
    before = dict()
    following = list()
    # A list of strings with the "before" constraint applied.  This
    # starts in the randomized order, and then gets (minimally)
    # adjusted to meet the constraints.
    ordered = list()
    for c in chosen:
        if pool[c].follows is not None:
            following.append(c)
            continue
        ordered.append(c)
        candidates = BuildBefore(pool[c].before,pool)
        # Add the candidates to the before list for c, but not it's
        # equal to c
        before[c] = []
        for cand in candidates:
            if cand == c: continue
            before[c].append(cand)
    for c in chosen:
        candidates = BuildAfter(pool[c].after,pool)
        # Add "c" to the before list for any candidate that it comes
        # after.
        for cand in candidates:
                if cand == c: continue
                if cand not in before: continue
                before[cand].append(c)
    # Reorder so all of the "before" constraints are met.
    notOrderedYet = True
    while notOrderedYet and len(ordered)>1:
        notOrderedYet = False
        for i in range(0,len(ordered)):
            for j in range(i+1,len(ordered)):
                if ordered[i] not in before[ordered[j]]: continue
                notOrderedYet = True
                ordered[i], ordered[j] = ordered[j], ordered[i]
                break
            if notOrderedYet: break
    # Add back stuff in the follows list.
    out = []
    for elem in ordered:
        out.append(elem)
        for check in following:
            if out[-1] in pool[check].follows: out.append(check)
    return out

######################################################################
## An instance of the exam.
#
# This holds all of the information necessary to produce one version
# of the exam
class ExamInstance(object):
    ## A dictionary of version specifier values to be substituted in
    ## this version.
    def __init__(self,exam,version,copy):
        self.exam = exam
        self.copy = copy
        self.name = str(exam.baseName) + "-" + str(copy).zfill(4)
        self.version = version
        self.questionList = []
        self.globals = dict()

        # Fill the global instances with the constants and variables values
        for k in exam.templates: self.globals[k] = exam.templates[k]
        for k in exam.constants: self.globals[k] = exam.constants[k].get()
        for k in exam.variables: self.globals[k] = exam.variables[k].get()

        # Turn the version information into constant values and copy
        # into the global instances.  The order is important so that
        # the version information overrides the constants and
        # variables.
        v = dict()
        for k in version: v[k] = ConstantValue(k,version[k])
        v["TITLE"] = ConstantValue("TITLE",str(self.exam.title))
        v["COPY"] = ConstantValue("TITLE",str(self.copy))
        for k in v: self.globals[k] = v[k].get()

        # Choose the questions for this version of the exam.
        chosen = []
        for k,n in self.exam.questions.sequence:
            if options.allQuestions: count = 9999
            elif "Choose" in n: count = n["Choose"]
            else: count = 9999
            if "Choices" not in n: raise ValueError("Missing question choices")
            chosen += ChooseFromPool(self.exam.pool, n["Choices"], count)

        chosen = OrderChosen(chosen,self.exam.pool)

        out = "Version " + str(self.copy) + " -- "
        for choice in chosen:
            out += " " + choice
        wrapper = textwrap.TextWrapper(subsequent_indent = "      ")
        print(wrapper.fill(out))

        # Fill the question list
        for item in range(0,len(chosen)):
            choice = chosen[item]
            q = self.exam.pool[choice]
            ok = False
            brake = 10
            while not ok and brake > 0:
                question = QuestionInstance(self,q,item+1)
                ok = question.ValidateQuestion()
                brake = brake - 1
            if brake < 1: raise RuntimeError("Can't find good answers")
            self.questionList.append(question)

        questions = ""
        for question in self.questionList: questions += question.MakeQuestion()

        self.globals["QUESTIONS"] = str(questions)

    def MakeExam(self) -> str:
        exam = self.exam.examTemplate
        exam = ExpandString(exam,self.globals)
        return exam

    def ValidateExam(self):
        print("Validate",self.name)
        validExam = True
        for q in self.questionList:
            if not q.ValidateQuestion():
                validExam = False
                print("Invalid question", q.QuestionName())
        return validExam

    ## Return a CSV line suitable for including in an answer key
    def MakeKey(self,header=False) -> str:
        key = ""
        if header:
            key += "\"Copy\""
            key += ","
            key += "\"Questions\""
            key += ","
            key += "\"Answers\""
            key += ","
            key += "\"Basename\""
            key += ","
            key += "\"QuestionNames\""
            for k in self.version: key += ",\"" + k + "\""
            key += "\n"
            return key
        key += str(self.copy)
        key += "," + str(len(self.questionList))
        key += ",\""
        for q in self.questionList: key += q.CorrectAnswer() + ";"
        key += "\""
        key += ",\"" + self.name + "\""
        key += ",\""
        for q in self.questionList: key += q.QuestionName() + ";"
        key += "\""
        for k in self.version: key += ",\"" + str(self.version[k]) + "\""
        key += "\n"
        return key


## This holds all of the information necessary to produce one question.
#
# This is built from a Question object and represents one particular
# version of the question.  The Question object should be treated as
# immutable since it will be shared by all ExamInstance objects.  The
# QuestionInstance is not shared between exams.
#
class QuestionInstance(object):
    def __init__(self, examInstance, question, number):
        self.question = question
        self.number = number
        self.examInstance = examInstance
        self.exam = self.examInstance.exam
        self.answerList = []
        self.correctAnswer = ""
        self.locals = dict()

        # Copy the global instances into the local scope and then
        # override with the question constants and variables.
        ok = False
        self.locals.update(examInstance.globals)
        self.UpdateVariables()
        self.AddUniques()

        # Choose and order the answers.  Always select all answers!
        chosen = ChooseFromPool(self.question.answers,".*",9999)

        chosen = OrderChosen(chosen,self.question.answers)

        # Fill the question list
        correct = False
        item = "ABCDEFGHIJKLMN"  # Should be from exam!
        for i in range(0,len(chosen)):
            choice = chosen[i]
            a = self.question.answers[choice]
            if a.correct:
                self.correctAnswer += item[i]
                correct = True
            self.answerList.append(AnswerInstance(self,a,item[i]))
        if not correct: raise RuntimeError("Question without a correct answer")

        answers = ""
        for answer in self.answerList: answers += answer.MakeAnswer()
        self.locals["ANSWERS"] = str(answers)
        self.locals["NUMBER"] = str(self.number)

    def UpdateVariables(self):
        for k in self.question.constants:
            self.locals[k] = self.question.constants[k].get()
        for k in self.question.variables:
            self.locals[k] = self.question.variables[k].get()

    def AddUniques(self):
        brake = 100
        uniqueOK = False
        while not uniqueOK:
            uniqueOK = True
            uniq = dict()
            vals = dict()
            for k in self.question.unique:
                u = self.question.unique[k]
                s = ExpandString(str(u.get()),self.locals)
                if s in uniq: uniqueOK = False
                uniq[s] = k
                vals[k] = s
            if not uniqueOK:
                self.UpdateVariables()
                brake -= 1
            if brake < 0:
                print("Cannot find unique set of values for "
                      + self.question.name)
                for kk in self.question.variables:
                    print(kk,
                          ExpandString(str(self.question.variables[kk].get()),
                                       self.locals))
                for kk in self.question.constants:
                    print(kk,
                          ExpandString(str(self.question.constants[kk].get()),
                                       self.locals))
                print("Uniques ", vals)
                sys.exit(1)
        for s in uniq:
            self.locals[uniq[s]] = s

    def ValidateQuestion(self):
        aDict = dict()
        questionOK = True
        # Check if there are duplicate answers for the question.
        for answer in self.answerList:
            txt = answer.locals["TEXT"];
            txt = ExpandString(str(txt),answer.locals)
            if txt in aDict:
                questionOK = False;
                aDict[txt].append(answer)
            else:
                aDict[txt] = [answer]
        if questionOK: return questionOK
        # The question has duplicated answers.  Check each set of
        # duplicate answers, and if any of the set is the correct
        # answer mark all of the set as correct.
        for k in aDict:
            if len(aDict[k]) < 2: continue
            correctDuplicate = False
            for a in aDict[k]:
                if a.locals["ITEM"] in self.correctAnswer:
                    correctDuplicate = True
            if correctDuplicate:
                for a in aDict[k]:
                    print("Duplicate Answer",a.AnswerName(),a.locals["ITEM"])
                    if a.locals["ITEM"] not in self.correctAnswer:
                        self.correctAnswer += a.locals["ITEM"]
        # There is a question with multiple correct answers
        # (duplicates).  Flag that by marking the correct answer as
        # lower case.  When grading any lower case answer should be
        # considered correct. (e.g. "ab" means both a and b are
        # correct).
        if not questionOK and len(self.correctAnswer) > 1:
            self.correctAnswer = self.correctAnswer.lower()
        return questionOK

    ## Build a single question for the test.
    #
    # This builds a template string, and then substitutes
    #
    # - &{NAME}  : The question name
    # - &{NUMBER} : The question number
    # - &{POINTS} : The number of points that this question is worth
    # - &{TEXT}  : The question text
    # - &{FIGURE} : The name of a figure file (pdf), or it is not defined
    # - &{SOLUTION} : The text for the solution.
    # - &{ANSWERS} : A string with all of the answers for this question
    #         which is automatically built using AnswerInstance.
    #
    # All of the definitions from the questionInstance are also included.
    def MakeQuestion(self) -> str:
        question =  "%% Start Question " + self.question.name + "\n"
        if "FIGURE" not in self.locals: question += self.exam.questionTemplate
        else: question += self.exam.questionWithFigureTemplate
        question += "\n"
        question += "%% Finish Question " + self.question.name + "\n"
        question = ExpandString(question,self.locals)
        return question

    def QuestionName(self) -> str:
        return self.question.name

    def CorrectAnswer(self) -> str:
        return self.correctAnswer

## Hold all of the information necessary to print one answer.
class AnswerInstance(object):
    def __init__(self, questionInstance, answer, item):
        self.answer = answer
        self.questionInstance = questionInstance
        self.question = self.questionInstance.question
        self.examInstance = self.questionInstance.examInstance
        self.exam = self.examInstance.exam
        self.locals = dict();
        self.locals.update(self.questionInstance.locals)
        self.locals["ITEM"] = item
        self.locals["TEXT"] = self.text()
        if self.correct(): self.locals["CORRECT"] = "Correct"
        else: self.locals["CORRECT"] = "Wrong"

    def __str__(self): return self.text()

    def text(self): return str(self.answer.text)

    def correct(self): return self.answer.correct

    ## Build a single answer for the test.
    #
    # This builds a template string, and then substitutes
    #
    # - &{ITEM}  : The answer item (usually "A", "B", "C", etc)
    # - &{TEXT}  : The answer text
    # - &{CORRECT} : A string for if this is the correct answer.  It
    #        will be "Correct" for right answers, and "Wrong" for wrong
    #        answers.
    #
    # All of the definitions from the questionInstance are also included.
    def MakeAnswer(self):
        answer  = "%% Start answer " + self.answer.name + "\n"
        answer += self.exam.answerTemplate + "\n"
        answer += "%% Finish answer " + self.answer.name + "\n"
        answer = ExpandString(answer,self.locals)
        return answer

    def AnswerName(self) -> str :
        return self.answer.name

######################################################################
# The main code begins here.

copy = 0
key = ""
exams = []

if not options.pickle:
    # Read the exam description from a YAML file and generate the exams
    exam = Exam(options.file[0])

    for version in exam.versions.inputs:
        copy += 1
        inst = ExamInstance(exam, version, copy)
        exams.append(inst)
        if options.oneVersion: break

else:
    # Read an existing exam from a PICKLE file
    with open(options.file[0], "rb") as file: exams = pickle.load(file)

if len(exams) < 1:
    print("No exams generated")
    sys.exit(1)

# Add a line of labels for the answer key
key += exams[0].MakeKey(True)

# Print each copy of the exam and build the answer keys
invalidExam = 0
for inst in exams:
    if not inst.ValidateExam(): invalidExam += 1
    key += inst.MakeKey()
    if not options.dryRun:
        filename = inst.name+".tex"
        print("Write version to", filename)
        with open(filename,"w") as texFile:
            texFile.write(inst.MakeExam())

# Print the answer key
if not options.dryRun:
    filename = exams[0].exam.baseName+".key"
    print("Write answer key to", filename)
    with open(filename,"w") as file: file.write(key)

# Save the pickle (but not if we read from a pickle).
if not options.dryRun and not options.pickle:
    filename = exams[0].exam.baseName+".pickle"
    print("Pickle to", filename)
    with open(filename,"wb") as file: pickle.dump(exams,file)

if invalidExam > 0: print("WARNING: Invalid question on",invalidExam,"exams")

# A GPL3 License
#
# Copyright 2022 Clark McGrew
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see
# <https://www.gnu.org/licenses/>.

############################################################################
# End of exam-writer
############################################################################
