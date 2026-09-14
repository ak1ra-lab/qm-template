from qm_template.shell import flatten, pretty


def test_flatten_joins_groups_in_order():
    groups = [["qm", "create", "9000"], ["--name", "vm"], ["--template", "1"]]
    assert flatten(groups) == [
        "qm",
        "create",
        "9000",
        "--name",
        "vm",
        "--template",
        "1",
    ]


def test_pretty_renders_one_group_per_line():
    groups = [["qm", "create", "9000"], ["--name", "my vm"], ["--template", "1"]]
    assert (
        pretty(groups) == "qm create 9000 \\\n    --name 'my vm' \\\n    --template 1"
    )


def test_pretty_keeps_a_single_group_on_one_line():
    assert pretty([["qm", "create", "9000"]]) == "qm create 9000"
