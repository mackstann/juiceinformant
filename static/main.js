/* JS for cubism chart */

function horizon(title, seconds, height, selector)
{
    var maxwatts = 10000;

    var context = cubism.context()
        .serverDelay(1 * 1000)
        .clientDelay(0.5 * 1000)
        .step((seconds*1000) / document.body.offsetWidth) // ms per x-axis pixel
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
        .data([metric(title)])
      .enter().insert("div", ".bottom")
        .attr("class", "horizon")
        .call(context.horizon()
          .extent([0, maxwatts])
          .format(d3.format("f"))
          .colors(['#000', '#000', '#000', '#000',
                   '#a2b444', '#ddbb26', '#e96d0b', '#bd1805' ])
          .height(height));

    context.on("focus", function(i) {
      d3.selectAll(".value").style("right", i == null ? null : context.size() - i + "px");
    });

    function metric(metric_title) {
        var watts = 0;
        var last_blink;
        return context.metric(function(start, stop, step, callback) {
            var start = +start;
            var stop = +stop;
            var values = [];
            d3.csv('/logdata/cubism/start=' + start.toFixed(6) + '/stop=' + stop.toFixed(6) + '/title=' + metric_title,
                function(rows) {
                    while(start < stop)
                    {
                        while(rows.length && rows[0].Blah.split(' ')[0]*1000 < start)
                        {
                            var record = rows.shift();
                            var ts = record.Blah.split(' ')[0]*1000;
                            var wh = parseInt(record.Blah.split(' ')[1]);
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
                    if (!rows) return callback(new Error("unable to load rows"));
                    callback(null, values);
                }
            );
        }, metric_title);
    }
}

horizon('10m', 60*10, 250, '#horizon1');
horizon('24h', 60*60*24, 90, '#horizon2');
horizon('7d', 60*60*24*7, 90, '#horizon3');

function hdd_for_temps(min, max)
{
    var base = 70;
    if(min > base)
        return 0;
    if((max + min)/2.0 > base)
        return (base - min)/4.0;
    if(max >= base)
        return (base - min)/2.0 - (max - min)/4.0;
    if(max < base)
        return base - (max + min)/2.0;
}

/* JS for calendar chart */

var width = document.body.offsetWidth;
var height = 180;
var cellSize = (width/52) - 2.5;

var day = d3.time.format("%w"),
    week = d3.time.format("%U"),
    percent = d3.format(".1%"),
    format = d3.time.format("%Y-%m-%d");

//var color = d3.scale.quantize()
//    .domain([0, 85000])
//    .range(d3.range(10).map(function(d) { return "q" + d + "-11"; }));

var i = 0;
var color = d3.scale.quantize()
    .domain([0, 85000])
    .range(d3.range(16, 224).map(function(d) {
        // lightness is 25-50 
        var r = d;
        var g = d;
        var b = d;
        //console.log(r, g, b);
        var hdd = i % 30;
        r += hdd;
        g -= hdd;
        b -= hdd;
        //console.log(r, g, b);
        i++;
        return 'rgb(' + r + ', ' + g + ', ' + b + ')';
    }));

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

var day_g = svg.selectAll(".day")
    .data(function(d) { return d3.time.days(new Date(d, 0, 1), new Date(d + 1, 0, 1)); })
    .enter()
    .append("g")
    .attr("class", "day")
    .attr("transform", function(d) { return "translate(" + week(d) * cellSize + "," + day(d) * cellSize + ")"; })
    .attr("width", cellSize)
    .attr("height", cellSize)
    .datum(format);
  
  day_g.append("rect")
    .attr("class", "day")
    .attr("width", cellSize)
    .attr("height", cellSize);

day_g.append("title");

svg.selectAll(".month")
    .data(function(d) { return d3.time.months(new Date(d, 0, 1), new Date(d + 1, 0, 1)); })
  .enter().append("path")
    .attr("class", "month")
    .attr("d", monthPath);

var hdd, cdd;
d3.json("/hdd", function(error, json) {
    if (error) return console.warn(error);
    hdd = json;

    d3.json("/cdd", function(error, json) {
        if (error) return console.warn(error);
        cdd = json;

        d3.csv("/logdata/calendar").get(function(error, rows) {
          var data = d3.nest()
            .key(function(d) { return d.Date; })
            .rollup(function(d) { return d[0].Wh; })
            .map(rows);

          var month_kwh = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

          var fill_color_by_hdd_cdd = function (starting_value, d)
          {
                var r = starting_value;
                var g = starting_value;
                var b = starting_value;
                var net_hdd = (hdd[d] || 0) - (cdd[d] || 0);
                var toInt = function(x) { return x | 0; };
                if(net_hdd > 0)
                {
                    r -= toInt(net_hdd*6);
                    g -= toInt(net_hdd*5);
                    b += toInt(net_hdd*6);
                }
                else if(net_hdd < 0)
                {
                    r += toInt(Math.abs(net_hdd)*6);
                    g -= toInt(Math.abs(net_hdd)*5);
                    b -= toInt(Math.abs(net_hdd)*6);
                }
                r = Math.min(255, Math.max(0, r));
                g = Math.min(255, Math.max(0, g));
                b = Math.min(255, Math.max(0, b));
                return 'fill: rgb(' + r + ', ' + g + ', ' + b + ');';
          };

          day_g.select("g.day > rect")
            //.attr("class", function(d) { return "day " + color(data[d]); })
            .attr("style", function(d) { return fill_color_by_hdd_cdd(255, d); });

            day_g.filter(function(d) { return d in data; })
                .select("title")
                .text(function(d) {
                    var parts = d.split('-');
                    var monthNames = [ "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" ];
                    var kwh = data[d]/1000;
                    return monthNames[parts[1]-1] + " " + parseInt(parts[2]) + ": " + kwh.toFixed(1) + 'kWh';
                });

            day_g.filter(function(d) { return d in data; })
                .append("circle")
                    .attr("style", function(d) { return fill_color_by_hdd_cdd(128, d); })
                    .attr("cx", function(d) { return cellSize/2; })
                    .attr("cy", function(d) { return cellSize/2; })
                    .attr("r", function (d) {
                        var scaled = data[d]/85000.0;
                        var max_volume = 3.14 * Math.pow(cellSize/2.0, 2);
                        var volume = max_volume * scaled;
                        var radius = Math.sqrt(volume/3.14);
                        return radius;
                    });

        });
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

