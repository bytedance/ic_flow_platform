proc dump_fsdb {}  {

    fsdbAutoSwitchDumpfile  10240  wave.fsdb 10
    fsdbDumpvarsByFile "dump.txt"
}


set dump_wave_en 1

set argv [split $::argv]
foreach one $argv {
    if {[string equal {+wave_dump=0} $one]} {
        set dump_wave_en 0
    }
}

if { $dump_wave_en == 1} {

    dump_fsdb 


    ## check if there is a savefile
    if { [file exists savefile ] }  {
        restore savefile 
        run
    } else {
        run
        run 0
        save savefile
    	run
    }
} else {
        run
}

run
