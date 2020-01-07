import cfnresponse
import logging
import boto3
import datetime
logger = logging.getLogger(__name__)

def stack_exists(cf_client, stack_name):
    stack_status_codes = ['CREATE_COMPLETE',
                        'UPDATE_COMPLETE',
                        'UPDATE_ROLLBACK_COMPLETE',
                        'ROLLBACK_COMPLETE']
    for s in stacks_by_status(cf_client, stack_status_codes):
        if s.get('StackName', '') == stack_name:
            return s
    return None
def stacks_by_status(cf_client, status_include_filter):
    """
    ``status_include_filter`` should be a list ...
    """
    pages = cf_client.get_paginator('list_stacks').paginate(
        StackStatusFilter=status_include_filter)
    for page in pages:
        for s in page.get('StackSummaries', []):
            yield s
def parse_properties(properties):
    cf_params = {'Capabilities': ['CAPABILITY_IAM',
                                  'CAPABILITY_AUTO_EXPAND',
                                  'CAPABILITY_NAMED_IAM'],
                'DisableRollback': True
    }
    cf_params["Parameters"] = []
    for key, value in properties.items():
        if key == "StackName":
            cf_params["StackName"] = value
        elif key == "TemplateURL":
            cf_params["TemplateURL"] = value
        elif key == "NumStacks":
            cf_params["NumStacks"] = int(value)
        elif key == "KeyToUpdate":
            cf_params["KeyToUpdate"] = value
        elif key == "ServiceToken":
            print("Skipping over ServiceToken")
        else:
            temp = {'ParameterKey': key, 'ParameterValue': value}
            print(temp)
            cf_params["Parameters"].append(temp)
    return cf_params

def loop_child_stacks(cf_client, cf_params, action, now, end, **kwargs):
    waiter_array = []
    numStacks = 1
    current_numStacks = 0
    found = False
    counter = 0
    if "KeyToUpdate" in cf_params:
        print("in key to Update")
        for param in cf_params["Parameters"]:
            print(param)
            if param["ParameterKey"] == cf_params["KeyToUpdate"]:
                found = True
                break
            counter += 1
        del cf_params["KeyToUpdate"]
    if action == "update":
        if "NumStacks" in cf_params and "NumStacks" in old_params:
            print("current is {} and old is {}".format(cf_params["NumStacks"],old_params["NumStacks"]))
            if cf_params["NumStacks"] > old_params["NumStacks"]:
                numStacks = cf_params["NumStacks"]
                del cf_params["NumStacks"]
            else:
                print("Found old params higher")
                numStacks = old_params["NumStacks"]
                current_numStacks = cf_params["NumStacks"]
                del cf_params["NumStacks"]
    elif "NumStacks" in cf_params:    
        numStacks = cf_params["NumStacks"]
        del cf_params["NumStacks"]
    for x in range(numStacks):
        if found:
            cf_params["Parameters"][counter]["ParameterValue"] = str(x)
        original_name = cf_params["StackName"]
        cf_params["StackName"] = "{}-{}".format(cf_params["StackName"],x)
        stack = stack_exists(cf_client=cf_client, stack_name=cf_params["StackName"])
        cur_action = action
        stack_state = 'stack_create_complete'
        if 'old_params' in vars():
            print("action is {} and x is {} and old_params Numstacks {}".format(action,x,old_params["NumStacks"]))
        if action == "update":
            print(current_numStacks)
            if current_numStacks and (x+1) > current_numStacks:
                print("setting cur_action to delete")
                cur_action = "delete"
            else:
                cur_action = "create"
        if cur_action == "create" and stack == None:
            stack_result = cf_client.create_stack(**cf_params)
            waiter_array.append(cf_params["StackName"])
        
        elif cur_action == "delete" and stack:
            print("found and deleting stack")
            stack_result = cf_client.delete_stack(StackName=cf_params["StackName"])
            waiter_array.append(cf_params["StackName"])
            stack_state = 'stack_delete_complete'

        cf_params["StackName"] = original_name
    waiter = cf_client.get_waiter(stack_state)
    print(waiter.config)
    waiter.config.max_attempts = 10
    wait_to_complete(cf_client,waiter,waiter_array,now=now, end=end)
        
def wait_to_complete(cf_client,waiter, waiter_array, now, end):
    while( len(waiter_array) > 0 ):
        if now > end:
            print("Time has ran out to wait, must exit")
            break
        cur_waiter = waiter_array.pop()
        print('...waiting for stack to be ready...')
        try:
            waiter.wait(StackName=cur_waiter)
        except Exception:
            print("Caught exception in Waiter..")
        stack = stack_exists(cf_client=cf_client, stack_name=cur_waiter)

def handler(event,context):
    logger.debug(event)
    status = cfnresponse.SUCCESS
    now = datetime.datetime.now()
    end = datetime.datetime.now() + datetime.timedelta(minutes=14)
    try:
        cf_client = boto3.client('cloudformation')
        cf_params = parse_properties(event['ResourceProperties'])
        if event['RequestType'] == 'Delete':
            print("Inside delete")
            logger.info(event)
            loop_child_stacks(cf_client=cf_client, cf_params=cf_params,action="delete", now=now, end=end)
        elif event['RequestType'] == 'Update':
            old_params = parse_properties(event['OldResourceProperties'])
            print("Inside update and old_params is {}".format(old_params))
            loop_child_stacks(cf_client=cf_client, cf_params=cf_params,action="update", now=now, end=end, old_params=old_params)
        else:
            loop_child_stacks(cf_client=cf_client, cf_params=cf_params,action="create", now=now, end=end)
        print("Completed")
    except Exception:
        logging.error('Unhandled exception', exc_info=True)
        status = cfnresponse.FAILED
    finally:
        cfnresponse.send(event, context, status, {}, None)