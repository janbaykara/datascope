from __future__ import unicode_literals, absolute_import, print_function, division

import hashlib
import json
from copy import copy, deepcopy

import requests
import jsonschema
from jsonschema.exceptions import ValidationError as SchemaValidationError
from urlobject import URLObject
from bs4 import BeautifulSoup

from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

import jsonfield

from datascope.configuration import DEFAULT_CONFIGURATION
from core.utils import configuration
from core.exceptions import DSHttpError50X, DSHttpError40X


class HttpResource(models.Model):
    # TODO: make sphinx friendly and doc all methods
    """
    A representation of how to fetch/submit data from/to a HTTP resource.

    Stores the headers, body and status of responses. It acts as a wrapper around requests library and provides:
    - responses from database when retrieved before
    - hooks to work with continuation URL's in responses
    - hooks to work with authentication
    """

    # Identification
    uri = models.CharField(max_length=255, db_index=True, default=None)
    data_hash = models.CharField(max_length=255, db_index=True, default="")

    # Configuration
    config = configuration.ConfigurationField(
        config_defaults=DEFAULT_CONFIGURATION,
    )

    # Getting data
    request = jsonfield.JSONField(default=None)

    # Storing data
    head = jsonfield.JSONField(default=None)
    body = models.TextField(default=None)
    status = models.PositiveIntegerField(default=None)

    # Archiving fields
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    purge_at = models.DateTimeField(null=True, blank=True)

    # Retention
    retainer = GenericForeignKey(ct_field="retainer_type", fk_field="retainer_id")
    retainer_type = models.ForeignKey(ContentType, null=True)
    retainer_id = models.PositiveIntegerField(null=True)

    # Class constants that determine behavior
    URI_TEMPLATE = ""
    PARAMETERS = {}
    HEADERS = {}
    GET_SCHEMA = {
        "args": {},
        "kwargs": {}
    }
    POST_SCHEMA = {
        "args": {},
        "kwargs": {}
    }

    #######################################################
    # PUBLIC FUNCTIONALITY
    #######################################################
    # The get and post methods are the ways to interact
    # with the external resource.
    # Success and data are convenient to handle the results

    def send(self, method, *args, **kwargs):
        """

        :param args:
        :param kwargs:
        :return: HttpResource
        """
        if not self.request:
            self.request = self._create_request(method, *args, **kwargs)
            self.uri = HttpResource.uri_from_url(self.request.get("url"))
            self.data_hash = HttpResource.hash_from_data(
                self.request.get("data")
            )
        else:
            self.validate_request(self.request)

        self.clean()  # sets self.uri and self.data_hash based on request
        try:
            resource = self.__class__.objects.get(
                uri=self.uri,
                data_hash=self.data_hash
            )
            self.validate_request(resource.request)
        except self.DoesNotExist:
            resource = self

        if resource.success:
            return resource

        resource.request = resource.request_with_auth()
        resource._send()
        resource._handle_errors()
        return resource

    def get(self, *args, **kwargs):
        """

        :param args:
        :param kwargs:
        :return:
        """
        return self.send("get", *args, **kwargs)

    def post(self, *args, **kwargs):
        """

        :param args:
        :param kwargs:
        :return: HttpResource
        """
        return self.send("post", *args, **kwargs)

    @property
    def success(self):
        """
        Returns True if status is within HTTP success range
        """
        return 200 <= self.status < 209

    @property
    def content(self):
        """

        :return: content_type, data
        """
        if self.success:
            content_type = self.head["content-type"].split(';')[0]
            if content_type == "application/json":
                return content_type, json.loads(self.body)
            elif content_type == "text/html":
                return content_type, BeautifulSoup(self.body)
            else:
                return content_type, None
        return None, None

    @property
    def meta(self):
        """

        :return: None
        """
        return None

    def retain(self, retainer):
        self.retainer = retainer
        self.save()

    #######################################################
    # CREATE REQUEST
    #######################################################
    # A set of methods to create a request dictionary
    # The values inside are passed to the requests library
    # Override parameters method to set dynamic parameters

    def _create_request(self, method, *args, **kwargs):
        self._validate_input(method, *args, **kwargs)
        data = self.data(**kwargs) if not method == "get" else None
        return self.validate_request({
            "args": args,
            "kwargs": kwargs,
            "method": method,
            "url": self._create_url(*args),
            "headers": self.headers(),
            "data": data,
        }, validate_input=False)

    def _create_url(self, *args):
        url_template = copy(unicode(self.URI_TEMPLATE))
        url = URLObject(url_template.format(*args))
        params = url.query.dict
        params.update(self.parameters())
        url = url.set_query_params(params)
        return unicode(url)

    def headers(self):
        """

        :return:
        """
        return self.HEADERS

    def parameters(self):
        """

        :return: dict
        """
        return self.PARAMETERS

    def data(self, **kwargs):
        """

        :return:
        """
        return kwargs

    def create_request_from_url(self, url):
        raise NotImplementedError()

    def validate_request(self, request, validate_input=True):
        # Internal asserts about the request
        assert isinstance(request, dict), \
            "Request should be a dictionary."
        method = request.get("method")
        assert method, \
            "Method should not be falsy."
        assert method in ["get", "post"], \
            "{} is not a supported resource method.".format(request.get("method"))  # FEATURE: allow all methods
        if validate_input:
            self._validate_input(
                method,
                *request.get("args", tuple()),
                **request.get("kwargs", {})
            )
        # All is fine :)
        return request

    def _validate_input(self, method, *args, **kwargs):
        # Validations of external influence
        schemas = self.GET_SCHEMA if method == "get" else self.POST_SCHEMA  # FEATURE: allow all methods
        args_schema = schemas.get("args")
        kwargs_schema = schemas.get("kwargs")
        if args_schema is None and len(args):
            raise ValidationError("Received arguments for request where there should be none.")
        if kwargs_schema is None and len(kwargs):
            raise ValidationError("Received keyword arguments for request where there should be none.")
        if args_schema:
            try:
                jsonschema.validate(list(args), args_schema)
            except SchemaValidationError as ex:
                raise ValidationError(str(ex))
        if kwargs_schema:
            try:
                jsonschema.validate(kwargs, kwargs_schema)
            except SchemaValidationError as ex:
                raise ValidationError(str(ex))

    #######################################################
    # AUTH LOGIC
    #######################################################
    # Methods to enable auth for the resource.
    # Override auth_parameters to provide authentication.

    def auth_parameters(self):
        return {}

    def request_with_auth(self):
        url = URLObject(self.request.get("url"))
        params = url.query.dict
        params.update(self.auth_parameters())
        url = url.set_query_params(params)
        request = deepcopy(self.request)
        request["url"] = unicode(url)
        return request

    def request_without_auth(self):
        url = URLObject(self.request.get("url"))
        url = url.del_query_params(self.auth_parameters())
        request = deepcopy(self.request)
        request["url"] = unicode(url)
        return request

    #######################################################
    # NEXT LOGIC
    #######################################################
    # Methods to act on continuation for a resource
    # Override next_parameters to provide auto continuation

    def next_parameters(self):
        return {}

    def create_next_request(self):
        if not self.success or not self.next_parameters():
            return None
        url = URLObject(self.request.get("url"))
        params = url.query.dict
        params.update(self.next_parameters())
        url = url.set_query_params(params)
        request = deepcopy(self.request)
        request["url"] = unicode(url)
        return request

    #######################################################
    # PROTECTED METHODS
    #######################################################
    # Some internal methods for the get and post methods.

    def _send(self):
        """
        Does a get on the computed link
        Will set storage fields to returned values
        """
        assert self.request and isinstance(self.request, dict), \
            "Trying to make request before having a valid request dictionary."

        if self.session is None:
            self.session = requests.Session()

        method = self.request.get("method")
        data = self.request.get("data") if not method == "get" else None
        request = requests.Request(
            method=method,
            url=self.request.get("url"),
            headers=self.request.get("headers"),
            data=data
        )
        preq = request.prepare()
        response = self.session.send(preq, proxies=settings.REQUESTS_PROXIES, verify=settings.REQUESTS_VERIFY)

        self.head = dict(response.headers)
        self.status = response.status_code
        self.body = unicode(
            response.content, 'utf-8', errors='replace'  # HTML can have some weird bytes, so replace errors!
        )

    def _handle_errors(self):
        """
        Raises exceptions upon error statuses
        """
        class_name = self.__class__.__name__
        if self.status >= 500:
            message = "{} > {} \n\n {}".format(class_name, self.status, self.body)
            raise DSHttpError50X(message, resource=self)
        elif self.status >= 400:
            message = "{} > {} \n\n {}".format(class_name, self.status, self.body)
            raise DSHttpError40X(message, resource=self)
        else:
            return True

    #######################################################
    # DJANGO MODEL
    #######################################################
    # Methods and properties to tweak Django

    def __init__(self, *args, **kwargs):
        super(HttpResource, self).__init__(*args, **kwargs)
        self.session = kwargs.get("session")

    def clean(self):
        if self.request and not self.uri:
            uri_request = self.request_without_auth()
            self.uri = HttpResource.uri_from_url(uri_request.get("url"))
        if self.request and not self.data_hash:
            uri_request = self.request_without_auth()
            self.data_hash = HttpResource.hash_from_data(uri_request.get("data"))

    #######################################################
    # CONVENIENCE
    #######################################################
    # Some static methods to provide standardization

    @staticmethod
    def uri_from_url(url):
        url = URLObject(url)
        return unicode(url).replace(url.scheme + u"://", u"")

    @staticmethod
    def hash_from_data(data):
        if not data:
            return ""
        hsh = hashlib.sha1()
        hsh.update(json.dumps(data))
        return hsh.hexdigest()

    class Meta:
        abstract = True