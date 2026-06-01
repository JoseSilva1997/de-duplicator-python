from enum import Enum


class ContactField(Enum):
    """The recognised contact fields, each paired with a label and a list of header aliases.

    Member order reflects how commonly each field appears in real-world exports.
    Within each member, alias order matters: header_resolver takes the first alias
    that matches, so more specific aliases should come before broader ones.
    """

    FIRST_NAME = ("First Name", ("firstname", "name"))
    LAST_NAME = ("Last Name", ("lastname", "lname", "surname"))
    FULL_NAME = ("Full Name", ("fullname",))  # fallback when split names are absent; alias list is intentionally thin
    EMAIL = ("Email", ("email", "emailaddress", "emailenteremail"))  # last alias is a known export artefact
    COMPANY = ("Company", ("company", "organization", "companyname", "organisation"))
    JOB_TITLE = ("Job Title", ("jobtitle", "position", "job", "role"))
    COUNTRY = ("Country", ("country", "region", "countryname", "countryregion"))

    def __init__(self, label: str, aliases: tuple[str, ...]):
        self.label = label
        self.aliases = aliases
