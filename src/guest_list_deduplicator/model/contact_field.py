from enum import Enum


class ContactField(Enum):
    """Standard contact fields and their alias lists for header resolution.

    Entries are ordered by likelihood of occurrence in real-world data.
    Alias order within each field matters: the resolver walks fields then
    aliases, so earlier aliases win if multiple headers could map.
    """

    FIRST_NAME = ("First Name", ("firstname", "name"))
    LAST_NAME = ("Last Name", ("lastname", "lname", "surname"))
    FULL_NAME = ("Full Name", ("fullname",))
    EMAIL = ("Email", ("email", "emailaddress", "emailenteremail"))
    COMPANY = ("Company", ("company", "organization", "companyname", "organisation"))
    JOB_TITLE = ("Job Title", ("jobtitle", "position", "job", "role"))
    COUNTRY = ("Country", ("country", "region", "countryname", "countryregion"))

    def __init__(self, label: str, aliases: tuple[str, ...]):
        self.label = label
        self.aliases = aliases
