from legacy.processes.base import Process, Retrieve
from legacy.tasks import execute_process, extend_process
from legacy.helpers.data import count_2d_list


# TODO: Fix people suggestions that use old texts and new processes
class PeopleSuggestions(Process):

    HIF_person_lookup = 'WikiSearch'
    HIF_retrieve_categories = 'WikiCategories'
    HIF_retrieve_members = 'WikiCategoryMembers'

    def process(self):

        # Get process input
        query = self.config.query

        # Setup person retriever
        person_lookup_config = {
            "_link": self.HIF_person_lookup,
        }
        person_lookup_config.update(self.config.dict())
        person_lookup_retriever = Retrieve()
        person_lookup_retriever.setup(**person_lookup_config)

        # Setup person retriever
        categories_config = {
            "_link": self.HIF_retrieve_categories,
            "_context": query,  # here only to distinct inter-query retriever configs from each other
            "_extend": {
                "source": None,
                "target": None,
                "args": "title",
                "kwargs": {},
                "extension": "categories"
            }
        }
        categories_config.update(self.config.dict())
        categories_retriever = Retrieve()
        categories_retriever.setup(**categories_config)

        # Setup data retriever
        members_config = {
            "_link": self.HIF_retrieve_members,
            "_context": query,  # here only to distinct inter-query retriever configs from each other
            "_extend": {
                "source": None,
                "target": 'categories.*',
                "args": "categories.*.title",
                "kwargs": {},
                "extension": "members"
            }
        }
        members_retriever = Retrieve()
        members_retriever.setup(**members_config)

        # Start Celery task
        task = (
            execute_process.s(query, person_lookup_retriever.retain()) |
            extend_process.s(categories_retriever.retain()) |
            extend_process.s(members_retriever.retain())
        )()
        self.task = task

    def post_process(self):

        person_data = Retrieve().load(serialization=self.task.result).rsl
        members_count = count_2d_list(person_data['categories'], d2_list='members', d2_id="title").most_common(11)[1:]  # takes 10, but strips query person

        people = []
        for member, count in members_count:

            person = {
                "title": member,
                "matches": count,
                "categories": [],
            }

            for category in person_data['categories']:
                members = [mem['title'] for mem in category['members']]
                if person['title'] in members:
                    person['categories'].append(category['title'][9:])  # strips 'Category:'

            people.append(person)

        self.rsl = people

    class Meta:
        app_label = "legacy"
        proxy = True


class PeopleSuggestionsWikiData(Process):

    HIF_person_lookup = 'WikiSearch'
    HIF_person_claims = 'WikiDataClaims'
    HIF_claimers = 'WikiDataClaimers'

    def process(self):

        # Get process input
        query = self.config.query

        # Setup person retriever
        person_lookup_config = {
            "_link": self.HIF_person_lookup,
        }
        person_lookup_config.update(self.config.dict())
        person_lookup_retriever = Retrieve()
        person_lookup_retriever.setup(**person_lookup_config)

        # Setup data retriever
        person_claims_config = {
            "_link": self.HIF_person_claims,
            "_context": query,  # here only to distinct inter-query retriever configs from each other
            "_extend": {
                "source": None,
                "target": None,
                "args": "wikidata",
                "kwargs": {},
                "extension": "claims"
            }
        }
        person_claims_retriever = Retrieve()
        person_claims_retriever.setup(**person_claims_config)

        # Setup claimers finder
        claimers_config = {
            "_link": self.HIF_claimers,
            "_context": query,  # here only to distinct inter-query retriever configs from each other
            "_extend": {
                "source": None,
                "args": "claims.*",  # spawns extend processes for every claim
                "kwargs": {},
                "target": "claims.*",
                "extension": "claimers"
            }
        }
        claimers_retriever = Retrieve()
        claimers_retriever.setup(**claimers_config)

        # Start Celery task
        task = (
            execute_process.s(query, person_lookup_retriever.retain()) |
            extend_process.s(person_claims_retriever.retain()) |
            extend_process.s(claimers_retriever.retain())
        )()
        self.task = task

    def post_process(self):

        person_data = Retrieve().load(serialization=self.task.result).rsl
        people_raw = count_2d_list(person_data['claims'], d2_list='claimers').most_common(11)[1:]  # takes 10, but strips query person

        people = []
        for person_raw in people_raw:

            person = {
                "item": person_raw[0],
                "matches": person_raw[1],
                "properties": [],
                "items": []
            }

            for claim in person_data['claims']:
                if person['item'] in claim['claimers']:
                    person['properties'].append(claim['property'])
                    person['items'].append(claim['item'])

            people.append(person)

        self.rsl = people

    class Meta:
        app_label = "legacy"
        proxy = True