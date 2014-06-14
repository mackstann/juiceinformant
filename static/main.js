/* JS for cubism chart */

function horizon(name, seconds, height, selector)
{
    var maxwatts = 12000;

    var context = cubism.context()
        .serverDelay(1 * 1000)
        .clientDelay(1 * 1000)
        .step((seconds*1000) / 1000) // ms per x-axis pixel
        .size(document.body.offsetWidth); // width in pixels

    // div elements: top axis and bottom axis. they contain time labels.
    d3.select(selector).selectAll(".axis")
        .data(["top", "bottom"])
      .enter().append("div")
        .attr("class", function(d) { return d + " axis"; })
        .each(function(d) { d3.select(this).call(context.axis().ticks(10).orient(d)); });

    // vertical line when hovering
    d3.select(selector).append("div")
        .attr("class", "rule")
        .call(context.rule());

    // the colored chart area
    d3.select(selector).selectAll(".horizon")
        .data([metric(name)])
      .enter().insert("div", ".bottom")
        .attr("class", "horizon")
        .call(context.horizon()
          .extent([0, maxwatts])
          .format(d3.format("f"))
          .colors(['#000', '#000', '#000', '#000',
                   '#cedb9c', '#b5cf6b', '#8ca252', '#637939' ])
          .height(height));

    context.on("focus", function(i) {
      d3.selectAll(".value").style("right", i == null ? null : context.size() - i + "px");
    });

    function metric(metric_name) {
        var watts = 0;
        var last_blink;
        return context.metric(function(start, stop, step, callback) {
            var start = +start;
            var stop = +stop;
            var values = [];
            d3.json('/logdata/cubism/start=' + start.toFixed(6) + '/stop=' + stop.toFixed(6) + '/step=' + step.toFixed(6),
                function(response) {
                    var data = response.d;
                    while(start < stop)
                    {
                        while(data.length && data[0][1]*1000 < start)
                        {
                            var record = data.shift();
                            var ts = record[1]*1000;
                            var wh = parseInt(record[0].split(' ')[1]);
                            if(!isNaN(last_blink))
                            {
                                if(ts <= last_blink)
                                    continue;
                                var deltat = ts - last_blink;
                                var wh_per_ms = wh / deltat;
                                var wh_per_s = wh_per_ms * 1000;
                                var new_watts = wh_per_s * 3600;
                                watts = new_watts;

                            }
                            last_blink = ts;
                        }
                        values.push(watts);
                        start += step;
                    }
                    if (!data) return callback(new Error("unable to load data"));
                    callback(null, values);
                }
            );
        }, metric_name);
    }
}
horizon('10m', 60*10, 250, '#horizon1');
horizon('24h', 60*60*24, 90, '#horizon2');
horizon('7d', 60*60*24*7, 90, '#horizon3');

/* JS for calendar chart */

var width = document.body.offsetWidth;
var height = 180;
var cellSize = (width/52) - 2.5;

var day = d3.time.format("%w"),
    week = d3.time.format("%U"),
    percent = d3.format(".1%"),
    format = d3.time.format("%Y-%m-%d");

var color = d3.scale.quantize()
    .domain([10000, 85000])
    .range(d3.range(4).map(function(d) { return "q" + d + "-11"; }));

var svg = d3.select("#calendar").selectAll("svg")
    .data(d3.range(2014, (new Date()).getFullYear()+1))
  .enter().append("svg")
    .attr("width", width)
    .attr("height", height)
    .attr("class", "RdYlGn")
  .append("g")
    .attr("transform", "translate(" + ((width - cellSize * 53) / 2) + "," + (height - cellSize * 7 - 1) + ")");

svg.append("text")
    .attr("transform", "translate(-6," + cellSize * 3.5 + ")rotate(-90)")
    .style("text-anchor", "middle")
    .text(function(d) { return d; });

var rect = svg.selectAll(".day")
    .data(function(d) { return d3.time.days(new Date(d, 0, 1), new Date(d + 1, 0, 1)); })
  .enter().append("rect")
    .attr("class", "day")
    .attr("width", cellSize)
    .attr("height", cellSize)
    .attr("x", function(d) { return week(d) * cellSize; })
    .attr("y", function(d) { return day(d) * cellSize; })
    .datum(format);

rect.append("title")
    .text(function(d) { return d; });

svg.selectAll(".month")
    .data(function(d) { return d3.time.months(new Date(d, 0, 1), new Date(d + 1, 0, 1)); })
  .enter().append("path")
    .attr("class", "month")
    .attr("d", monthPath);

d3.csv("/logdata/calendar").get(function(error, rows) {
  var data = d3.nest()
    .key(function(d) { return d.Date; })
    .rollup(function(d) { return d[0].Wh; })
    .map(rows);

  var month_kwh = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

  rect.filter(function(d) { return d in data; })
    .attr("class", function(d) { return "day " + color(data[d]); })
    .select("title")
    .text(function(d) {
        var parts = d.split('-');
        var monthNames = [ "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" ];
        var kwh = data[d]/1000;
        return monthNames[parts[1]-1] + " " + parseInt(parts[2]) + ": " + kwh.toFixed(1) + 'kWh';
    });
});

function monthPath(t0) {
  var t1 = new Date(t0.getFullYear(), t0.getMonth() + 1, 0),
      d0 = +day(t0), w0 = +week(t0),
      d1 = +day(t1), w1 = +week(t1);
  return "M" + (w0 + 1) * cellSize + "," + d0 * cellSize
      + "H" + w0 * cellSize + "V" + 7 * cellSize
      + "H" + w1 * cellSize + "V" + (d1 + 1) * cellSize
      + "H" + (w1 + 1) * cellSize + "V" + 0
      + "H" + (w0 + 1) * cellSize + "Z";
}

d3.select(self.frameElement).style("height", "2910px");

