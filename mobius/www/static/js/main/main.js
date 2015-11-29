require([
    'dojo/dom',
    'stream/stream',
    'dojo/domReady!'
],
function(dom, stream)
{
    var upload_stream = new stream.Stream("upload_progress");
    upload_stream.register(function(message)
    {
        console.log(message);
    });
});
