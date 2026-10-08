import os
import shutil
from pytest_bdd import scenarios, given, when, then
scenarios('features/runtime.feature')
@given('the Docker application environment')
def docker_environment():
    assert os.path.exists('/.dockerenv')
@when('I inspect its dependency location',target_fixture='dependency_location')
def location():
    return os.environ.get('UV_PROJECT_ENVIRONMENT')
@then('the virtual environment is stored under opt')
def isolated(dependency_location):
    assert dependency_location == '/opt/venv'
@then('the invest entry point is available')
def executable():
    assert shutil.which('invest') == '/opt/venv/bin/invest'
