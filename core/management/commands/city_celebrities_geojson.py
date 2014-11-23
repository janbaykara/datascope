from geojson import Point, Feature, FeatureCollection, dumps as geodump

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Turns City Celebrities Service output into geojson encoded data.
    """

    def handle(self, *args, **kwargs):
        """

        :param args:
        :param kwargs:
        :return:
        """
        self.args = "<city_name>/<lat>|<lon> <city_name>/<lat>|<lon> ..."

        # Import models here to prevent circular imports
        from core.output.http.services.manifests import CityCelebritiesService

        if not args:
            print("You'll need to specify coordinates like: London/51.5286416|-0.1015987/100")
            return

        for arg in args:

            # Start the process
            city, coords, radius = arg.split('/')
            city_celebrities = CityCelebritiesService()
            city_celebrities.setup(query=unicode(city))

            features = []
            for location in city_celebrities.content:
                point = Point((location['lon'], location['lat'],))
                feature = Feature(geometry=point, properties={
                    'title': location['title'],
                    'people': ', '.join([person['title'] for person in location['people']])
                })
                features.append(feature)

            collection = FeatureCollection(features)
            print geodump(collection)
