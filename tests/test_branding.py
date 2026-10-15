from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tomllib import loads

from bs4 import BeautifulSoup
from platformdirs import user_config_path, user_data_path
from pytest_bdd import given, scenarios, then, when

scenarios("features/branding.feature")


@when("I inspect the packaged local page", target_fixture="page")
def inspect_page():
    import invest

    return (Path(invest.__file__).parent / "static" / "index.html").read_text()


@then("its title and brand name are Investobot")
def page_brand(page):
    parsed = BeautifulSoup(page, 'html.parser')
    assert parsed.title.get_text(strip=True) == 'Investobot · Local portfolio'
    assert 'Investobot' in list(parsed.body.stripped_strings)
    assert 'Invest Copilot' not in parsed.get_text()


@given("no explicit path overrides")
def defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("INVEST_DB", raising=False)
    monkeypatch.delenv("INVEST_CONFIG", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    path = user_config_path("investobot") / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text('[branding]\nname = "Investobot"\n')


@when(
    "I inspect the default ledger and load the default configuration",
    target_fixture="defaults_result",
)
def default_paths():
    from invest.config import database_path, load_config

    return database_path(), load_config()


@then("the ledger and configuration use Investobot directories")
def configured(defaults_result):
    path, config = defaults_result
    assert path == user_data_path("investobot") / "portfolio.db"
    assert config["branding"]["name"] == "Investobot"


@when("I inspect installed package metadata", target_fixture="distribution_version")
def distribution():
    try:
        return version("investobot")
    except PackageNotFoundError:
        return None


@then("the Investobot distribution is installed")
def installed(distribution_version):
    project = loads((Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text())['project']
    assert project['name'] == 'investobot'
    assert distribution_version == project['version']
