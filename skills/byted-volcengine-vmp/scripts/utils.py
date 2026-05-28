import asyncio
from multiprocessing.pool import AsyncResult

import six
import volcenginesdkcore


class UniversalApi(volcenginesdkcore.UniversalApi):
    def __init__(self, api_client=None):
        super().__init__(api_client)

    async def do_call_async(self, info, body, **kwargs):  # noqa: E501
        kwargs['async_req'] = True
        result = self.do_call(info, body, **kwargs)
        return await wait_for_async_result(result)

    def do_call_with_http_info(self, info, body, **kwargs):  # noqa: E501
        all_params = ['body', 'query', 'async_req', '_return_http_data_only', '_preload_content',
                      '_request_timeout']  # noqa: E501

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method do_call" % key
                )
            params[key] = val
        del params['kwargs']

        # verify the required parameter 'body' is set
        if self.api_client.client_side_validation and ('body' not in params or
                                                       params['body'] is None):  # noqa: E501
            raise ValueError(
                "Missing the required parameter `body` when calling `do_call`")  # noqa: E501

        # if type(params['body']) is not dict:
        #    raise TypeError(
        #        "The required parameter `body` must be dict")  # noqa: E501

        collection_formats = {}

        path_params = {}

        query_params = []

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        if 'body' in params:
            body_params = params['body']

        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json'])  # noqa: E501

        if info.content_type is not None:
            # HTTP header `Content-Type`
            header_params['Content-Type'] = self.api_client.select_header_content_type(  # noqa: E501
                [info.content_type])  # noqa: E501

        if info.method.lower() == "get":
            query_params = list(body.items())

        # Authentication setting
        auth_settings = ['volcengineSign']  # noqa: E501

        path = '/' + info.action + '/' + info.version + '/' + info.service + '/' + info.method.lower() + '/'
        return self.api_client.call_api(
            path, info.method.upper(),
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type=object,  # noqa: E501
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=params.get('_return_http_data_only'),
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)

async def wait_for_async_result(async_result: AsyncResult):
    while not async_result.ready():
        # check if the async result is ready every 100ms
        await asyncio.sleep(0.1)
    return async_result.get()