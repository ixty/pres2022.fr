function dateToYMD(date)
{
    var d = date.getDate();
    var m = date.getMonth() + 1;
    var y = date.getFullYear();
    return '' + y + '-' + (m<=9 ? '0' + m : m) + '-' + (d <= 9 ? '0' + d : d);
}

function get_hidden_candidates()
{
    var hidden_candidates = (localStorage.getItem('hidden_candidates') || 'montebourg,bertrand,taubira').split(',');
    if(!hidden_candidates)
        hidden_candidates = [];
    return hidden_candidates;
}

function fmt_num(n)
{
    if(n >= 1000)
        return (n / 1000.0).toFixed(1) + 'K';
    return n;
}

function zeropad(num, places)
{
    return String(num).padStart(places, '0');
}

function add_days(date, days)
{
    var res = new Date(date);
    res.setDate(res.getDate() + days);
    day = res.getFullYear() + '-' + zeropad(res.getMonth()+1, 2) + '-' + zeropad(res.getDate(), 2);
    if(day < day_min)
        day = day_min;
    if(day > day_max)
        day = day_max;
    return day;
}

function day_diff(dstr1, dstr2)
{
    var d1 = new Date(dstr1);
    var d2 = new Date(dstr2);
    return Math.ceil((d1 - d2) / (1000 * 60 * 60 * 24));
}

function dday1(dstr)
{
    return 'J' + day_diff(dstr, '2022-04-10') + ' <small>(1<sup>er</sup> tour)</small>';
}

function ddayprog(dstr)
{
    return 100 * day_diff(dstr, day_min) / day_diff(day_max, day_min);
}
