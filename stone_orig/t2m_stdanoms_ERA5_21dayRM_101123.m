% (1) Bring in ERA5 t2m, lat, lon, time
% Open t2m, time, lat, lon data
t2m_link = dir('/glade/scratch/jackstone/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/*.nc');
Nfiles = length(t2m_link);
all_t2m = cell(Nfiles,1); all_time = cell(Nfiles,1);
for i = 1:Nfiles  
    all_t2m{i} = ncread(strcat(t2m_link(i).folder,'/',t2m_link(i).name), 'VAR_2T');
    all_time{i} = ncread(strcat(t2m_link(i).folder,'/',t2m_link(i).name), 'time');
end
t2m = double(squeeze(cat(3,all_t2m{:})));
timevar = squeeze(cat(1,all_time{:})); timevar_h = datetime(1900,1,1) + hours(timevar);
lonvar = ncread('/glade/scratch/jackstone/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/199001.nc', 'longitude');
latvar = ncread('/glade/scratch/jackstone/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/199001.nc', 'latitude');

% Subset to 25-90 N
latind = find(latvar >= 25);
latvar = latvar(latind);
t2m = t2m(:,latind,:);

% Detrend
t2m_de = detrend(t2m);

% Calculate mean, stdev for each day-of-year
mon_day = double(string(month(timevar_h))+'999'+string(day(timevar_h)));
group_mean = zeros(size(t2m_de));
group_std = zeros(size(t2m_de));
for i = 1:length(mon_day)
    idx = find(mon_day == mon_day(i));
    group_mean(:,:,i) = mean(t2m_de(:,:,idx),3);
    group_std(:,:,i) = std(t2m_de(:,:,idx),[],3);
    disp(string(100.*i./length(mon_day)))
end
% Apply running means
group_mean = squeeze(movmean(group_mean,21,3));
group_std = squeeze(movmean(group_std,21,3));


% Subset everything to DJF
djf_ind = find(month(timevar_h) == 12 | month(timevar_h) == 1 | month(timevar_h) == 2);
timevar = timevar(djf_ind);
timevar_h = timevar_h(djf_ind);
group_mean = group_mean(:,:,djf_ind);
group_std = group_std(:,:,djf_ind);
t2m_de = t2m_de(:,:,djf_ind);

% Calculate standardized anomalies
t2m_stdanom = (t2m_de - group_mean)./group_std;

% Save each winter as a file (i.e. 197912-198002 is one nc file)
    % Include proper metadata
for i = 1979:2020
    if i+1 == 1980 || i+1 ==  1984 || i+1 ==  1988 || i+1 ==  1992 || i+1 ==  1996 || i+1 ==  2000 || i+1 ==  2004 || i+1 ==  2008 || i+1 ==  2012 || i+1 ==  2016 || i+1 ==  2020
        timeind = zeros(91,1);
        timeind = find(timevar_h == datetime('01-Dec-'+string(i)+' 11:00:00')):find(timevar_h == datetime('29-Feb-'+string(i+1)+' 11:00:00'));
    else
        timeind = zeros(90,1);
        timeind = find(timevar_h == datetime('01-Dec-'+string(i)+' 11:00:00')):find(timevar_h == datetime('28-Feb-'+string(i+1)+' 11:00:00'));
    end

    t2m_stdanom_sub = t2m_stdanom(:,:,timeind);
    timevar_sub = timevar(timeind);

    file_link = '/glade/scratch/jackstone/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/t2m_stdanoms/'+string(i)+'_'+string(i+1)+'.nc';
    
    nccreate(file_link,'t2m_stdanom','Dimensions', {'lon',size(t2m_stdanom_sub,1),'lat',size(t2m_stdanom_sub,2),'time',Inf}); 
    nccreate(file_link,'time','Dimensions', {'time',Inf}); 
    nccreate(file_link,'lat','Dimensions', {'lat',size(t2m_stdanom_sub,2)}); 
    nccreate(file_link,'lon','Dimensions', {'lon',size(t2m_stdanom_sub,1)}); 
    
    ncwrite(file_link,'t2m_stdanom',t2m_stdanom_sub);
    ncwriteatt(file_link, 't2m_stdanom', 'units', 'K');
    ncwrite(file_link,'time',timevar_sub);
    ncwriteatt(file_link, 'time', 'units', 'hours since 1900-01-01');
    ncwrite(file_link,'lat',latvar);
    ncwrite(file_link,'lon',lonvar);

end
