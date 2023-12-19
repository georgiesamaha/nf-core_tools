"""
Lint the main.nf file of a subworkflow
"""

import logging
import re

log = logging.getLogger(__name__)


def main_nf(_, subworkflow):
    """
    Lint a ``main.nf`` subworkflow file

    Can also be used to lint local subworkflow files,
    in which case failures will be reported as
    warnings.

    The test checks for the following:

    * A subworkflow SHOULD import at least two modules
    * All included modules or subworkflows are used and their names are used for `versions.yml`
    * The workflow name is all capital letters
    * The subworkflow emits a software version
    """

    inputs = []
    outputs = []

    # Read the lines directly from the subworkflow
    lines = None
    if lines is None:
        try:
            # Check whether file exists and load it
            with open(subworkflow.main_nf, "r") as fh:
                lines = fh.readlines()
            subworkflow.passed.append(("main_nf_exists", "Subworkflow file exists", subworkflow.main_nf))
        except FileNotFoundError:
            subworkflow.failed.append(("main_nf_exists", "Subworkflow file does not exist", subworkflow.main_nf))
            return

    # Go through subworkflow main.nf file and switch state according to current section
    # Perform section-specific linting
    state = "subworkflow"
    subworkflow_lines = []
    workflow_lines = []
    main_lines = []
    for l in lines:
        if re.search(r"^\s*workflow\s*\w*\s*{", l) and state == "subworkflow":
            state = "workflow"
        if re.search(r"take\s*:", l) and state in ["workflow"]:
            state = "take"
            continue
        if re.search(r"main\s*:", l) and state in ["take", "workflow"]:
            state = "main"
            continue
        if re.search(r"emit\s*:", l) and state in ["take", "main", "workflow"]:
            state = "emit"
            continue

        # Perform state-specific linting checks
        if state == "subworkflow" and not _is_empty(l):
            subworkflow_lines.append(l)
        if state == "workflow" and not _is_empty(l):
            workflow_lines.append(l)
        if state == "take" and not _is_empty(l):
            inputs.extend(_parse_input(subworkflow, l))
        if state == "emit" and not _is_empty(l):
            outputs.extend(_parse_output(subworkflow, l))
        if state == "main" and not _is_empty(l):
            main_lines.append(l)

    # Check that we have required sections
    if not len(outputs):
        subworkflow.failed.append(("main_nf_script_outputs", "No workflow 'emit' block found", subworkflow.main_nf))
    else:
        subworkflow.passed.append(("main_nf_script_outputs", "Workflow 'emit' block found", subworkflow.main_nf))

    # Check the subworkflow include statements
    included_components = check_subworkflow_section(subworkflow, subworkflow_lines)

    # Check the workflow definition
    check_workflow_section(subworkflow, workflow_lines)

    # Check the main definition
    check_main_section(subworkflow, main_lines, included_components)

    # Check that a software version is emitted
    if outputs:
        if "versions" in outputs:
            subworkflow.passed.append(
                ("main_nf_version_emitted", "Subworkflow emits software version", subworkflow.main_nf)
            )
        else:
            subworkflow.warned.append(
                ("main_nf_version_emitted", "Subworkflow does not emit software version", subworkflow.main_nf)
            )

    return inputs, outputs


def check_main_section(self, lines, included_components):
    """
    Lint the main section of a subworkflow
    Checks whether all included components are used and their names are used for `versions.yml`.
    """
    # Check that we have a main section
    if len(lines) == 0:
        self.failed.append(
            (
                "main_section",
                "Subworkflow does not contain a main section",
                self.main_nf,
            )
        )
        return
    self.passed.append(("main_section", "Subworkflow does contain a main section", self.main_nf))

    script = "".join(lines)

    # Check that all included components are used
    # Check that all included component versions are used
    if included_components is not None:
        for component in included_components:
            if component in script:
                self.passed.append(
                    ("main_nf_include_used", f"Included component '{component}' used in main.nf", self.main_nf)
                )
            else:
                self.warned.append(
                    (
                        "main_nf_include_used",
                        f"Included component '{component}' not used in main.nf",
                        self.main_nf,
                    )
                )
            if component + ".out.versions" in script:
                self.passed.append(
                    (
                        "main_nf_include_versions",
                        f"Included component '{component}' versions are added in main.nf",
                        self.main_nf,
                    )
                )
            else:
                self.warned.append(
                    (
                        "main_nf_include_versions",
                        f"Included component '{component}' versions are not added in main.nf",
                        self.main_nf,
                    )
                )


def check_subworkflow_section(self, lines):
    """Lint the section of a subworkflow before the workflow definition
    Specifically checks if the subworkflow includes at least two modules or subworkflows

    Args:
        lines (List[str]): Content of subworkflow.

    Returns:
        List: List of included component names. If subworkflow doesn't contain any lines, return None.
    """
    # Check that we have subworkflow content
    if len(lines) == 0:
        self.failed.append(
            (
                "subworkflow_include",
                "Subworkflow does not include any modules before the workflow definition",
                self.main_nf,
            )
        )
        return
    self.passed.append(
        ("subworkflow_include", "Subworkflow does include modules before the workflow definition", self.main_nf)
    )

    includes = []
    for l in lines:
        if l.strip().startswith("include"):
            component_name = l.split("{")[1].split("}")[0].strip()
            if " as " in component_name:
                component_name = component_name.split(" as ")[1].strip()
            includes.append(component_name)
    if len(includes) >= 2:
        self.passed.append(("main_nf_include", "Subworkflow includes two or more modules", self.main_nf))
    else:
        self.warned.append(("main_nf_include", "Subworkflow includes less than two modules", self.main_nf))

    return includes


def check_workflow_section(self, lines):
    """Lint the workflow definition of a subworkflow before
    Specifically checks that the name is all capital letters

    Args:
        lines (List[str]): Content of workflow definition.

    Returns:
        None
    """
    # Workflow name should be all capital letters
    self.workflow_name = lines[0].split()[1]
    if self.workflow_name == self.workflow_name.upper():
        self.passed.append(("workflow_capitals", "Workflow name is in capital letters", self.main_nf))
    else:
        self.failed.append(("workflow_capitals", "Workflow name is not in capital letters", self.main_nf))


def _parse_input(self, line):
    """
    Return list of input channel names from a take section.
    """
    inputs = []
    # Remove comments and trailing whitespace
    inputs.append(line.split("//")[0].strip())
    return inputs


def _parse_output(self, line):
    output = []
    if len(line) > 0:
        output.append(line.split("=")[0].strip())
    return output


def _is_empty(line):
    """Check whether a line is empty or a comment"""
    empty = False
    if line.strip().startswith("//"):
        empty = True
    if line.strip().replace(" ", "") == "":
        empty = True
    return empty