.PHONY: testbench clean dut uvm elab simv


TEST_NAME = adder_base_test
TEST_TYPE = normal_test
CMP_OPTS_USER = +define+CMP_OPTS_USER_NULL_NULL
SEED = 0
XPROP = XPROP_OFF_NULL


SIM_OPTS = -ucli \
		   -i run.do \
		   +ntb_random_seed=${SEED} \
		   -cm line+cond+fsm+tgl+branch+assert 

CMP_OPTS = -xlrm uniq_prior_final \
		   -full64 \
		   -kdb \
		   -notice \
		   +vcs+lic+wait \
		   +v2k \
		   +verilog2001ext+.vp \
		   -debug_access+pp+f  \
		   -sverilog \
		   -error=IPDW \
		   -error=IGPA \
		   -error=PCSRMIO \
		   -error=AOUP \
		   -error=ELW_UNBOUND \
		   -error=IUWI \
		   -error=INAV \
		   -error=ENUMASSIGN \
		   -error=SV-ISC \
		   -error=OSVF-NPVIUFPI \
		   -error=DPIMI \
		   -error=IPDASP \
		   -error=CM-HIER-FNF \
		   -error=CWUC \
		   -error=UPF_OBJECT_NOT_FOUND_WARN \
		   -error=CIWC \
		   -error=MATN \
		   -error=SV-IIS \
		   -error=WUIMCM \
		   -error=CPBRM \
		   -error=NMCM \
		   -error=CEPO \
		   +warn=noZONMCM \
		   +warn=noTMR \
		   +nowarnTFMPC \
		   -suppress=LCA_FEATURES_ENABLED \
		   -suppress=UII-L \
		   -suppress=UPF_SUPPLY_PORT_IMPLICIT_CONNECTION \
		   -suppress=PCTIO-L \
		   -suppress=SV-LCM-PPWI \
		   -suppress=SVA-LDRF \
		   -suppress=VCM-NOCOV-ENC \
		   -suppress=VCM-NODRCO \
		   +lint=TFIPC \
		   -ucli  \
		   -lca \
		   +vpi \
		   -timescale=1ns/1ps \
		   -licwait	30	\
		   -diag timescale \
		   +notimingcheck \
		   +nospecify \
		   +no_notifier \
		   -ntb_opts uvm \
		   +libext+.v+.V+.sv+.vh+.svh \
		   +define+ASSERT_ON \
		   +define+FAST_LINK \
		   -cm line+cond+fsm+tgl+branch+assert \
		   -cm_line contassign \
		   ${CMP_OPTS_USER}

ELAB_OPTS = -full64 \
		   -debug_access+r  \
		   -ntb_opts uvm \
		   +vcs+lic+wait \
		   -diag timescale \
		   -lca -kdb \
		   -cm line+cond+fsm+tgl+branch+assert \
		   -cm_line contassign  
		   
ELAB_XPROP_OPTS = -full64 \
		   -debug_access+pp+f  \
		   -ntb_opts uvm \
		   +vcs+lic+wait \
		   -diag timescale \
		   -lca -kdb \
		   -cm line+cond+fsm+tgl+branch+assert \
		   -cm_line contassign  \

all : comp  elab simv
all_xprop : comp  elab_xprop simv


comp : dut uvm testbench

dut :
	vlogan ${CMP_OPTS} \
	-f ${PROJ_PATH}/design/dut.f \
	-l dut.log

uvm : 
	vlogan  ${CMP_OPTS} 

testbench :
	vlogan ${CMP_OPTS} \
	-f ${PROJ_PATH}/verif/tb/tb.f \
	-l tb.log

elab :
	vcs  ${ELAB_OPTS} -top tb_top -o simv -l elab.log


simv : 
	./simv ${SIM_OPTS}  +UVM_TESTNAME=${TEST_NAME} +svt_enable_pa=FSDB  -l sim.log +factor=1 +NO_EQ +TEST_TYPE=${TEST_TYPE}


clean :
	rm work* -rf
	rm *.fsdb -rf
	rm AN.DB -rf
	rm *.log -rf
	rm simv* -rf
	rm verdi* -rf
	rm verilog* -rf
	rm novas* -rf
	rm wave.vf -rf
	rm csrc -rf
	rm *.h -rf
	rm ucli.key -rf



