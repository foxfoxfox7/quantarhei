"""

    Autogenerated by ghenerate script, part of Quantarhei
    http://github.com/tmancal74/quantarhei
    Tomas Mancal, tmancal74@gmai.com

    Generated on: 2018-06-04 13:53:49

    Edit the functions below to give them desired functionality.
    In present version of `ghenerate`, no edits or replacements
    are perfomed in the feature file text.

"""
import os

from subprocess import check_output
#from subprocess import call

from behave import given
from behave import when
from behave import then

import quantarhei.tests.testing.behave as bhv

#
# Given ...
#
@given('that Quantarhei is installed')
def step_given_1(context):
    """Step implementation for:

        Given that Quantarhei is installed

    """

    # if this does not break, quantarhei is installed
    bhv.quantarhei_installed(context)


#
# When ...
#
@when('I run the ghenerate script')
def step_when_1(context):
    """Step implementation for:

        When I run the ghenerate script

    """
    output = check_output("ghenerate")
    context.output = output


#
# Then ...
#
@then('I get a simple usage message')
def step_then_1(context):
    """Step implementation for:

        Then I get a simple usage message

    """
    bhv.check_output_contains(context, "No file specified: quiting\nusage:",
                               err_msg="No usage message returned")


#
# And ...
#
@given('current directory contains a feature file')
def step_given_2(context):
    """Step implementation for:

        And current directory contains a feature file

    """

    bhv.secure_temp_dir(context)

    with bhv.testdir(context):
        ffile = "test.feature"
        bhv.fetch_test_feature_file(context, ffile)

        if not os.path.isfile(ffile):
            raise Exception("Feature file: "+ffile+" not found")


#
# And ...
#
@given('the default destination directory exists')
def step_given_3(context):
    """Step implementation for:

        And the default destination directory exists

    """
    from pathlib import Path

    with bhv.testdir(context):
        path = os.path.join(context.tempdir.name, "ghen")
        my_file = Path(path)
        if not my_file.exists():
            my_file.mkdir()

        if not my_file.is_dir():
            raise Exception("Defailt destination directory does not exist.")


#
# When ...
#
@when('I run the ghenerate script with the name of the feature file')
def step_when_2(context):
    """Step implementation for:

        When I run the ghenerate script with the name of the feature file

    """

    context.feature_file = "test.feature"
    context.step_file = "test.py"

    with bhv.testdir(context):

        bhv.shell_command(context, "ghenerate "+context.feature_file,
                          err_msg="Command ghenerate "+context.feature_file+
                          " failed")


#
# Then ...
#
@then('feature file is converted into a Python step file')
def step_then_2(context):
    """Step implementation for:

        Then feature file is converted into a Python step file

    """

    # this will remain empty, there is no way how this can be checked
    context.output = ""

#
# And ...
#
@then('the step file is saved into default destination directory')
def step_then_3(context):
    """Step implementation for:

        And the step file is saved into default destination directory

    """

    with bhv.testdir(context):

        ffile = os.path.join("ghen", context.step_file)
        print(ffile)
        if not os.path.isfile(ffile):
            raise Exception("Step file: "+ffile+" not found")

    bhv.cleanup_temp_dir(context)


#
# And ...
#
@given('{destination_directory} exists')
def step_given_4(context, destination_directory):
    """Step implementation for:

        And {destination_directory} exists

    """
    from pathlib import Path

    with bhv.testdir(context):

        my_file = Path(destination_directory)
        my_file.mkdir()
        context.dest = destination_directory

        if not my_file.is_dir():
            raise Exception("Destination directory "+destination_directory+
                            " does not exist")


#
# When ...
#
@when('I run {ghenerate_command} with the option specifying destination directory')
def step_when_4(context, ghenerate_command):
    """Step implementation for:

        When I run {ghenerate_command} with the option specifying destination directory

    """

    context.step_file = os.path.join(context.dest, "test.py")

    with bhv.testdir(context):

        ghencom = ghenerate_command+" "+"test.feature"
        err_msg = "Command "+ghenerate_command+" failed"

        bhv.shell_command(context, ghencom, err_msg=err_msg)



#
# And ...
#
@then('step file is saved into the destination directory')
def step_then_4(context):
    """Step implementation for:

        And step file is saved into the destination directory

    """
    step_file = context.step_file

    with bhv.testdir(context):

        if not os.path.isfile(step_file):
            raise Exception("step file not found")

    bhv.cleanup_temp_dir(context)


#
# And ...
#
@given('the {destination_directory} does not exist')
def step_given_5(context, destination_directory):
    """Step implementation for:

        And the {destination_directory} does not exist

    """
    context.dest = destination_directory

    with bhv.testdir(context):

        if os.path.isdir(destination_directory):
            raise Exception("directory "+destination_directory+
                            " must NOT be present for this test to start")


#
# Then ...
#
@then('destination directory is created')
def step_then_5(context):
    """Step implementation for:

        Then destination directory is created

    """
    dest = context.dest

    with bhv.testdir(context):

        if not os.path.isdir(dest):
            raise Exception("directory "+dest+" was not found")
