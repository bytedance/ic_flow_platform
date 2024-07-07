<style>
img{
    width: 55%;
    padding-left: 25%;
}
</style>

# Rusage Memory Data Analysis

## data source
- from $START_DATE to $END_DATE

## I Overall Analysis

### 1.1 overall histogram

- **x** : memory interval （unit：GB）
- **y**:  job num

![avatar]($OVERALL_HISTOGRAM)

### 1.2 overall scatter

- **x**: true max memory（unit：GB）
- **y**: rusage memory（unit：GB）
- **green line** : when true max memory is equal to rusage memory

![avatar]($OVERALL_SCATTER)

### 1.3 rusage difference sum

- **x**: memory interval （unit：TB）
- **y**: rusage and true memory difference sum（unit：GB）

![avatar]($DIFFERENCE_SUM_HISTOGRAM)


### 1.4 rusage difference in value

- **x**: memory interval （unit：GB）
- **y**: rusage and true memory difference in value（unit：GB）

![avatar]($DIFFERENCE_VALUE_HISTOGRAM)

### 1.5 rusage difference in rate

- **x**:  memory interval （unit：GB）
- **y**:  rusage and true memory difference in rate（unit：GB）

![avatar]($DIFFERENCE_RATE_HISTOGRAM)

### 1.6 non rusage memory analysis

- **x**: memory interval (unit : GB)
- **y**: non-rusage memory count

![avatar]($NON_RUSAGE_MEMORY_HISTOGRAM) 

### 1.7 total reservation difference with true memory

- the total over-reservation memory(unit: TB): 

$TOTAL_OVER_RUSAGE_MEMORY_TABLE

- the total under-reservation memory(unit: TB): 

$TOTAL_UNDER_RUSAGE_MEMORY_TABLE


## II analysis based on user

- **over_rusage_sum**
  - the sum of (rusage memory - max memory ) group by user when the user rusage memory > true max memory
- **over_rusage_mem**
  - the mean of (rusage memory - max memory ) group by user when the user rusage memory > true max memory
- **over_rusage_num**
  - the number of job  when rusage memory > max memory

### 2.1 tolerance pie chat


- filter top 15 **not_tolerance_over_rusage_sum** user

![avatar]($TOLERANCE_RUSAGE_USER_PIE)


### 2.2 table

- filter top 15 **not_tolerance_over_rusage_sum** user list

$TOLERANCE_PIE_CHART_TABLE

