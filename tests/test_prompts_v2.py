import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.models import DomainError

scenarios("features/prompts_v2.feature")


@pytest.fixture
def ctx(tmp_path):
    from invest.prompts import PromptLibrary

    directory = tmp_path / "prompts"
    return {"library": PromptLibrary(directory), "directory": directory, "tmp": tmp_path}


def capture(ctx, operation):
    try:
        ctx["result"] = operation()
    except DomainError as exc:
        ctx["error"] = exc


@when("I list the local prompt library")
def listed(ctx):
    ctx["result"] = ctx["library"].list()


@then("all nine investment workflow prompts are available")
def defaults(ctx):
    assert {item["id"] for item in ctx["result"]} == {
        "tax-loss-harvesting", "portfolio-concentration", "fund-comparison",
        "stock-research", "bond-research", "target-generation", "tax-aware-rebalancing",
        "alternative-portfolios", "recent-developments",
    }
    assert all(item["source"] == "bundled" for item in ctx["result"])


@then("reading the library creates no user directory")
def no_creation(ctx):
    assert not ctx["directory"].exists()


@when("I read the concentration prompt")
def read_default(ctx):
    ctx["result"] = ctx["library"].show("portfolio-concentration")


@then("its complete text contains portfolio analysis and human control instructions")
def text(ctx):
    content = ctx["result"]["content"]
    assert content.startswith("# ")
    assert "concentration" in content.lower()
    assert "human" in content.lower()
    assert "invest" in content
    assert len(content) > 200


@when("I save and edit a personal prompt")
def edit(ctx):
    ctx["library"].save("my-review", "# My review\nFirst version.\n")
    ctx["library"].save("my-review", "# My review\nUpdated full text.\n")


@then("its latest full text is available")
def edited(ctx):
    result = ctx["library"].show("my-review")
    assert result["content"] == "# My review\nUpdated full text.\n"
    assert result["source"] == "user"


@when("I delete the personal prompt")
def deleted(ctx):
    ctx["library"].delete("my-review")


@then("it is no longer available")
def absent(ctx):
    assert "my-review" not in {item["id"] for item in ctx["library"].list()}
    with pytest.raises(DomainError):
        ctx["library"].show("my-review")


@when("I override and then remove the concentration prompt")
def override(ctx):
    ctx["original"] = ctx["library"].show("portfolio-concentration")["content"]
    ctx["library"].save("portfolio-concentration", "# Custom concentration\nMy instructions.")
    assert ctx["library"].show("portfolio-concentration")["bundled_available"] is True
    ctx["library"].delete("portfolio-concentration")


@then("the original bundled text is restored")
def restored(ctx):
    assert ctx["library"].show("portfolio-concentration")["content"] == ctx["original"]


@then("deleting the bundled original is rejected")
def immutable(ctx):
    with pytest.raises(DomainError):
        ctx["library"].delete("portfolio-concentration")
    assert ctx["library"].show("portfolio-concentration")["content"] == ctx["original"]


@when(parsers.parse('I save a prompt named "{slug}"'))
def unsafe(ctx, slug):
    capture(ctx, lambda: ctx["library"].save(slug, "# Review\nInstructions."))


@then("a prompt input error prevents the write")
def invalid(ctx):
    assert isinstance(ctx.get("error"), DomainError)
    assert ctx["error"].code == 1
    assert not (ctx["directory"] / "my-review.md").exists()


@given("a prompt file symlink to an outside document")
def symlink_file(ctx):
    ctx["directory"].mkdir()
    ctx["outside"] = ctx["tmp"] / "outside.md"
    ctx["outside"].write_text("Private document.", encoding="utf-8")
    (ctx["directory"] / "private.md").symlink_to(ctx["outside"])


@when("I try to read edit and delete the symlink prompt")
def symlink_operations(ctx):
    for operation in (
        lambda: ctx["library"].show("private"),
        lambda: ctx["library"].save("private", "Replacement"),
        lambda: ctx["library"].delete("private"),
        lambda: ctx["library"].list(),
    ):
        with pytest.raises(DomainError):
            operation()


@then("every operation is rejected and the outside file is unchanged")
def outside_safe(ctx):
    assert ctx["outside"].read_text(encoding="utf-8") == "Private document."
    assert (ctx["directory"] / "private.md").is_symlink()


@given("the configured prompt directory is a symlink")
def symlink_directory(ctx):
    outside = ctx["tmp"] / "outside"
    outside.mkdir()
    ctx["directory"].symlink_to(outside, target_is_directory=True)


@when("I save a personal prompt")
def save(ctx):
    capture(ctx, lambda: ctx["library"].save("my-review", "# My review\nInstructions."))


@when("I save a prompt larger than 64 KiB")
def large(ctx):
    capture(ctx, lambda: ctx["library"].save("my-review", "€" * 22000))


@given("the prompt directory is configured by environment")
def configured(ctx, monkeypatch):
    from invest.prompts import PromptLibrary

    monkeypatch.setenv("INVEST_PROMPTS", str(ctx["directory"]))
    ctx["library"] = PromptLibrary()


@then("it is stored in that configured directory")
def stored(ctx):
    assert (ctx["directory"] / "my-review.md").read_text(encoding="utf-8") == (
        "# My review\nInstructions."
    )
