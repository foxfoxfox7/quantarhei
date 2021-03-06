"""

    Autogenerated by ghenerate script, part of Quantarhei
    http://github.com/tmancal74/quantarhei
    Tomas Mancal, tmancal74@gmai.com

    Generated on: 2018-06-06 15:00:05

    Edit the functions below to give them desired functionality.
    In present version of `ghenerate`, no edits or replacements
    are perfomed in the feature file text.

"""

import os

from behave import given
from behave import when
from behave import then

import quantarhei.testing.behave as bhv

#
# Given ...
#
@given('that I have a list of examples from qrhei list')
def step_given_1(context):
    """

        Given that I have a list of examples from qrhei list

    """
    bhv.secure_temp_dir(context)

    with bhv.testdir(context):
        bhv.shell_command(context, "qrhei list --examples")
        
        text = context.output.decode("utf-8")
        items = text.split()
        
        files_to_fetch = []
        for item in items:
            if item.startswith("ex_"):
                files_to_fetch.append(item)
            
        context.files = files_to_fetch


#
# When ...
#
@when('I fetch all examples one by one')
def step_when_2(context):
    """

        When I fetch all examples one by one

    """
    
    failures = []
    
    with bhv.testdir(context):
        for file in context.files:
            bhv.shell_command(context, "qrhei fetch --examples "+file)
            print(context.output.decode("utf-8"))
          
        if not os.path.isfile(file):
            failures.append("File: "+file+" was not fetched")
            
    context.failures = failures


#
# Then ...
#
@then('examples are all fetchable')
def step_then_3(context):
    """

        Then examples are all fetchable

    """
    if len(context.failures) > 0:
        raise Exception("some examples are not fetchable: "
                        +str(context.failures))
