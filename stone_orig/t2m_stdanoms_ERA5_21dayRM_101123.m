% (1) Bring in ERA5 t2m, lat, lon, time
% Open t2m, time, lat, lon data
disp('Starting')
t2m_link = dir('/glade/derecho/scratch/zarzycki/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/*.nc');
Nfiles = length(t2m_link);
all_t2m = cell(Nfiles,1); all_time = cell(Nfiles,1);
for i = 1:Nfiles
    fprintf('Processing file %d/%d: %s\n', i, Nfiles, t2m_link(i).name);
    all_t2m{i} = ncread(strcat(t2m_link(i).folder,'/',t2m_link(i).name), 'VAR_2T');
    all_time{i} = ncread(strcat(t2m_link(i).folder,'/',t2m_link(i).name), 'time');
end
disp('Squeezing')
t2m = double(squeeze(cat(3,all_t2m{:})));
timevar = squeeze(cat(1,all_time{:})); timevar_h = datetime(1900,1,1) + hours(timevar);
lonvar = ncread('/glade/derecho/scratch/zarzycki/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/199001.nc', 'longitude');
latvar = ncread('/glade/derecho/scratch/zarzycki/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/199001.nc', 'latitude');

% CMZ, show me what the t2m shape is...
size(t2m)

% Subset to 25-90 N
disp('Subsetting')
latind = find(latvar >= 25);
latvar = latvar(latind);
t2m = t2m(:,latind,:);

% Detrend
disp('Detrending')
% -----
% Original Stone code
%t2m_de = detrend(t2m);
% -----
% CMZ new code to permute since detrend works on first dimension and time needs to be dim 1
t2m_perm    = permute(t2m, [3 1 2]);          % (time, lon, lat)
t2m_de_perm = detrend(t2m_perm);             % linear detrend along dim 1 = time
t2m_de      = ipermute(t2m_de_perm, [3 1 2]); % back to (lon, lat, time)
% CMZ (debugging, turn off trending)
%t2m_de = t2m;
% -----

% Calculate mean, stdev for each day-of-year
disp('Stats')
mon_day = double(string(month(timevar_h))+'999'+string(day(timevar_h)));
group_mean = zeros(size(t2m_de));
group_std = zeros(size(t2m_de));
for i = 1:length(mon_day)
    idx = find(mon_day == mon_day(i));
    group_mean(:,:,i) = mean(t2m_de(:,:,idx),3);
    group_std(:,:,i) = std(t2m_de(:,:,idx),[],3);
    disp(string(100.*i./length(mon_day)))

    fprintf('Completed %d/%d (%.1f%%)\n', ...
        i, length(mon_day), 100*i/length(mon_day));
end

% CMZ some more shape metrics
size(group_mean)
size(group_std)

% Apply running means
% CMZ commented out
group_mean = squeeze(movmean(group_mean,21,3));
group_std = squeeze(movmean(group_std,21,3));

% Subset everything to DJF
disp('More subsetting')
djf_ind = find(month(timevar_h) == 12 | month(timevar_h) == 1 | month(timevar_h) == 2);
timevar = timevar(djf_ind);
timevar_h = timevar_h(djf_ind);
group_mean = group_mean(:,:,djf_ind);
group_std = group_std(:,:,djf_ind);
t2m_de = t2m_de(:,:,djf_ind);

% Calculate standardized anomalies
disp('Std anom calc')
t2m_stdanom = (t2m_de - group_mean)./group_std;

% Save each winter as a file (i.e. 197912-198002 is one nc file)
    % Include proper metadata
disp('Saving')
for i = 1979:2020
    fprintf('Processing winter season %d-%d (%d/%d)\n', i, i+1, i-1978, 2020-1979+1);
    if i+1 == 1980 || i+1 ==  1984 || i+1 ==  1988 || i+1 ==  1992 || i+1 ==  1996 || i+1 ==  2000 || i+1 ==  2004 || i+1 ==  2008 || i+1 ==  2012 || i+1 ==  2016 || i+1 ==  2020
        timeind = zeros(91,1);
        timeind = find(timevar_h == datetime('01-Dec-'+string(i)+' 11:00:00')):find(timevar_h == datetime('29-Feb-'+string(i+1)+' 11:00:00'));
    else
        timeind = zeros(90,1);
        timeind = find(timevar_h == datetime('01-Dec-'+string(i)+' 11:00:00')):find(timevar_h == datetime('28-Feb-'+string(i+1)+' 11:00:00'));
    end

    t2m_stdanom_sub  = t2m_stdanom(:,:,timeind);
    t2m_raw_sub      = t2m(:,:,timeind);
    t2m_de_sub       = t2m_de(:,:,timeind);
    clim_mean_sub    = group_mean(:,:,timeind);
    clim_std_sub     = group_std(:,:,timeind);
    timevar_sub      = timevar(timeind);

    file_link = '/glade/derecho/scratch/zarzycki/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/t2m_stdanoms/'+string(i)+'_'+string(i+1)+'.nc';

    % CMZ -- purge any existing file
    if isfile(file_link)
        delete(file_link)
    end

    nt = length(timeind);
    nd = size(t2m_stdanom_sub, 1);
    nl = size(t2m_stdanom_sub, 2);
    % 'Format','classic' forces netCDF-3, avoiding a MATLAB HDF5 dimension-scale
    % bug (NC_EDIMSCALE) that fires when multiple variables share dimensions.
    % Only the first nccreate call needs it — it sets the file format at creation.
    nccreate(file_link,'t2m_stdanom',  'Dimensions', {'lon',nd,'lat',nl,'time',nt}, 'Format','classic');
    nccreate(file_link,'t2m_raw',      'Dimensions', {'lon',nd,'lat',nl,'time',nt});
    nccreate(file_link,'t2m_detrended','Dimensions', {'lon',nd,'lat',nl,'time',nt});
    nccreate(file_link,'clim_mean',    'Dimensions', {'lon',nd,'lat',nl,'time',nt});
    nccreate(file_link,'clim_std',     'Dimensions', {'lon',nd,'lat',nl,'time',nt});
    nccreate(file_link,'time','Dimensions', {'time',nt});
    nccreate(file_link,'lat', 'Dimensions', {'lat',nl});
    nccreate(file_link,'lon', 'Dimensions', {'lon',nd});

    ncwrite(file_link,'t2m_stdanom',  t2m_stdanom_sub);
    ncwriteatt(file_link,'t2m_stdanom',  'units','sigma');
    ncwriteatt(file_link,'t2m_stdanom',  'long_name','Standardized 2m temperature anomaly');
    ncwrite(file_link,'t2m_raw',      t2m_raw_sub);
    ncwriteatt(file_link,'t2m_raw',      'units','K');
    ncwriteatt(file_link,'t2m_raw',      'long_name','Raw daily 2m temperature');
    ncwrite(file_link,'t2m_detrended',t2m_de_sub);
    ncwriteatt(file_link,'t2m_detrended','units','K');
    ncwriteatt(file_link,'t2m_detrended','long_name','Detrended daily 2m temperature');
    ncwrite(file_link,'clim_mean',    clim_mean_sub);
    ncwriteatt(file_link,'clim_mean',    'units','K');
    ncwriteatt(file_link,'clim_mean',    'long_name','Smoothed climatological mean (detrended)');
    ncwrite(file_link,'clim_std',     clim_std_sub);
    ncwriteatt(file_link,'clim_std',     'units','K');
    ncwriteatt(file_link,'clim_std',     'long_name','Smoothed climatological std (detrended)');
    ncwrite(file_link,'time',timevar_sub);
    ncwriteatt(file_link,'time','units','hours since 1900-01-01');
    ncwrite(file_link,'lat',latvar);
    ncwrite(file_link,'lon',lonvar);

end
