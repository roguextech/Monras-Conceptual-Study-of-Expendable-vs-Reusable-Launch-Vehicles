import numpy as np
import matplotlib.pyplot as plt
import sys
import aerocalc
import scipy.integrate as scip_int



"""
Version 4.2 
"""
def rho_calc(alt):
    """Calculates the air density at the given altitude"""
    if alt >= 80000:
        # if over 80 000m, no atmosphere
        # rho = 0
        rho = 0
    elif alt < 0:
        #print("under ground!")
        rho = 0
    else:
        rho = aerocalc.std_atm.alt2density(alt, alt_units='m', density_units='kg/m**3')
    return rho

def ascent(t, Y):
    """Returns an update array using the previous data entered and the equations stated here, all for the ascen"""
    # Y = [V, gamma, X, H, m]
    V = Y[0]
    gam = Y[1]
    H = Y[3]
    m = Y[4]

    # thrust
    if 0 <= t <= t_bo:
        T = Isp * g0 * beta
    else:
        T = 0  # meaning the rocket has burnt out, T = 0
    # drag
    rho = rho_calc(H)

    # Calculates new forces
    D = 0.5 * rho * (r ** 2 * np.pi) * Cd * (V ** 2)  # Drag
    g = g0 * ((R_earth / (H + R_earth)) ** 2)  # gravity

    # Activates gravity turn if G_T_bool = True
    if G_T_bool:
        gam_dot = - np.cos(gam) * (g - V**2/(R_earth + H))/V
    else:
        gam_dot = 0

    # use the steering law for the last stage
    if Last_Stage_bool:
        gam_dot = 0
        gam = np.arctan(np.tan(gam_last_stage_i)*(1 - (t/t_bo)))

    #print("gam_dot: ", gam_dot)
    # Calculates dY change
    V_dot = T / m - D / m - g * np.sin(gam)
    x_dot = (R_earth / (R_earth + H)) * V * np.cos(gam)  # transforms to ground range speed
    h_dot = V * np.sin(gam)

    V_dot_grav = - g * np.sin(gam)
    V_dot_drag = - D / m
    V_dot_thrust = T / m


    # save data for plots
    g_arr.append(g/g0)
    T_arr.append(T/1000)
    gam_arr.append(gam*180/np.pi)
    D_arr.append(D/1000)
    Time_arr.append(t)
    V_arr.append(V/1000)
    H_arr_plot.append(H/1000)
    gam_dot_arr.append(gam_dot)
    mass_arr.append(m/1000)

    dY = [V_dot, gam_dot, x_dot, h_dot, -beta, V_dot_grav, V_dot_drag, V_dot_thrust]
    return dY

def reentry(t, Y):
    """Returns an updated increment array of the one entered for the ballistic re-entry phase of the trajectory"""
    # Y = [V, gamma, X, H, m]
    V = Y[0]
    gam = Y[1]
    H = Y[3]
    m = Y[4]

    # no thrust for re-entry
    # beta = 0
    rho = rho_calc(H)

    # Calculates new forces
    D = 0.5 * rho * (r ** 2 * np.pi) * Cd * (V ** 2)  # Drag
    g = g0 * ((R_earth / (H + R_earth)) ** 2)  # gravity

    V_dot = - D / m - g * np.sin(gam)
    gam_dot = - np.cos(gam) * (g - V ** 2 / (R_earth + H)) / V
    x_dot = (R_earth / (R_earth + H)) * V * np.cos(gam)  # transforms to ground range speed
    h_dot = V * np.sin(gam)
    dY = [V_dot, gam_dot, x_dot, h_dot, 0, 0, 0, 0]

    return dY

def hit_ground(t, Y):
    """Checks if the object hits the ground"""
    return Y[3]
def zero_velocity(t, Y):
    """Checks if the object has zero velocity"""
    return Y[0]

def calc_Q(H, V):
    """Calculates the heating rate using the H calculated for re-entry stage"""
    Q_arr = []
    Q_arr_calc = []
    length = len(H)
    # find index where H = 80 000
    for j in H:
        if j <= 80000:
            touple = np.where(H==j)
            index = touple[0][0]
            break
        else:
            index = 0
    V_arr_re.append(V[index]/1000)
    for i in range(index, length):
        # drag
        rho = rho_calc(H[i])
        q = (1.83 * 10 ** -4) * (V[i] ** 3) * np.sqrt(rho / r_nose)/10000  # in [W/cm^2]
        Q_arr.append(q)
        q_calc = q * 10000 * r_nose**2*np.pi / 1000000  # [MJ]
        Q_arr_calc.append(q_calc)
    Q_tot = sum(Q_arr_calc )

    return index, Q_arr, Q_tot


def calc_reentry(Y_re_i, n_stages):
    """Calculates the re-entry dynamics"""
    # Y_staging = [Stage1, Stage2, Satellite]
    # Y_re = [V, gamma, X, H, m]
    for i_re in range(0, n_stages):
       #print("reentry stage: ", i_re + 1)
        t_bo_re = T_BO_arr[i_re]
        Y_re = Y_re_i[i_re]
        if i_re == 0:
            # retro landing of first stage!
            Y_re[4] = M_s[i_re] + mp1_retro    # ms1 + mp1_retro
            # Solve the ODE until it hits the ground or simulation time runs out
            hit_ground.terminal = True
            hit_ground.direction = -1
            zero_velocity.terminal = True
            zero_velocity.direction = -1
            sol_re = scip_int.solve_ivp(retro_landing, (t_bo_re, t_sim), Y_re, method="RK45", max_step=0.05, events=[hit_ground, zero_velocity])
        elif i_re == 1:
            # Initialize reverse burn on last stage!
            V_i_rev = Y_re_i[i_re][0] + reverse_burn
            Y_re[0] = V_i_rev
            Y_re[1] = 0
            Y_re[4] = M_s_re[i_re]
            # print("Y_re: ", Y_re)
            # Solve the ODE until it hits the ground or simulation time runs out
            hit_ground.terminal = True
            hit_ground.direction = -1
            sol_re = scip_int.solve_ivp(ascent, (t_bo_re, t_sim), Y_re, method="RK45", max_step=1, events=hit_ground)

        # Save data for the re-entry
        #print("Stage landing time: ", sol_re.t[-1])
        X_arr_re.append(sol_re.y[2] / 1000)  # saves the current solutions position of the stages
        H_arr_re.append(sol_re.y[3] / 1000)
        Q_arr_re.append(calc_Q(sol_re.y[3], sol_re.y[0]))

    return X_arr_re, H_arr_re, Q_arr_re

def retro_landing(t,Y):
    """Calculates the new delta V for the landing with boosters and fuel left"""
    # Y = [V, gamma, X, H, m]
    V = Y[0]
    gam = Y[1]
    X = Y[2]
    H = Y[3]
    m = Y[4]
    #print("Mass landing: ", m)
    # no thrust for re-entry!
    # thrust
    if 0 < H < H_start_retro_booster and V > 0:
        if m > ms1:
            # if we havent burnt up all the propellant
            #thrust between t_bo1 and landing
            T = - Isp1 * g0 * beta_retro
            beta = beta_retro
        else:
            T = 0  # meaning the rocket has burnt out, T = 0
            beta = 0
    else:
       T = 0  # meaning the rocket has burnt out, T = 0
       beta = 0


    # beta = 0
    rho = rho_calc(H)

    # Calculates new forces
    D = 0.5 * rho * (r ** 2 * np.pi) * Cd * (V ** 2)  # Drag
    g = g0 * ((R_earth / (H + R_earth)) ** 2)  # gravity

    V_dot = T / m - D / m - g * np.sin(gam)
    gam_dot = - np.cos(gam) * (g - V ** 2 / (R_earth + H)) / V
    x_dot = (R_earth / (R_earth + H)) * V * np.cos(gam)  # transforms to ground range speed
    h_dot = V * np.sin(gam)
    dY = [V_dot, gam_dot, x_dot, h_dot, -beta, 0, 0, 0]
    Time_arr_retro.append(t)
    V_arr_retro.append(V/1000)
    H_arr_retro.append(H/1000)
    T_arr_retro.append(T/1000)
    gam_arr_retro.append(gam*180/np.pi)
    m_arr_retro.append(m/1000)
    X_arr_retro.append(X/1000)
    return dY


if __name__ == '__main__':
    # ascent
    X_arr = []
    H_arr = []
    g_arr = []
    T_arr = []
    gam_arr = []
    D_arr = []
    Time_arr = []
    V_arr = []
    H_arr_plot = []
    gam_dot_arr = []
    mass_arr = []
    markers_pos = []
    markers_time = []
    Y_staging = []      # Y_staging = [Stage1, Stage2, Stage3, Satellite]
    V_drag_arr = []
    V_gravity_arr = []
    V_thrust_arr = []
    Y_i_arr = []        # Saves the conditions for each seperation/staging

    # re-entry
    X_arr_re = []
    H_arr_re = []
    Q_arr_re = []
    V_arr_re = []
    V_arr_retro = []
    V_tot_arr = []
    Time_arr_retro = []
    H_arr_retro = []
    T_arr_retro = []
    gam_arr_retro = []
    m_arr_retro = []
    X_arr_retro = []
    # Constants
    G = 6.67408e-11  # [m**3*kg**-1*s**-2]
    g0 = 9.81  # [m/s^2]
    Cd = 0.3  # drag coefficient
    M_earth = 5.9723e24  # [kg]
    R_earth = 6371e3  # [m]
    w_earth = 7.27e-5  # Earth angular speed
    V_earth = w_earth*R_earth / 1000

    # Targeted orbit velocity
    V_c = np.sqrt(G * M_earth/(R_earth + 600000))/1000
    V_esc = np.sqrt(2*G * M_earth/(R_earth + 600000))/1000

    # Initial values for stages
    Csteel = 510  #  [J/kgK]
    # payload (satellite)
    mpay = 1000  # [kg]
    rpay = 1    # [m]
    r = 2.5 / 2  # [m]
    r_nose = 1   # [m]

    # stage 2
    ms2 = 267.8694832  # [kg]
    mp2 = 6490         # [kg]
    m02 = ms2 + mp2 + mpay
    t_bo2 = 426  # [s]
    Isp2 = 348  # [s]
    beta2 = mp2 / t_bo2  # [kg/s]
    reverse_burn = -150   # [m/s]

    # stage 1
    ms1 = 4174.054467 # [kg]
    mp1 = 64252.81638 # [kg]
    Isp1 = 297.5       # [s]
    t_bo1 = 163       # [s]
    m01 = ms1 + mp1 + m02
    beta1 = mp1*0.9 / t_bo1    # Only burning 90 % of the propellant! [kg/s]

    # retro landing conditions
    t_bo_retro = 30
    mp1_retro = mp1*0.1
    beta_retro = mp1_retro/t_bo_retro
    mo_retro = ms1 + mp1_retro
    H_start_retro_booster = 23*1000  # [m]


    # Set the gravity turn conditions
    gam_g_t = 88*np.pi/180
    t_gt = 21.8   # [s]

    # Total simulation running time
    t_sim = 3600

    # Rocket conditions
    M = [m01, m02, mpay]        # rockets masses
    M_s = [ms1, ms2, 0]        # 1st stage mass has the saved propellant included!
    M_s_re = [ms1, ms2, mpay]
    ISP = [Isp1, Isp2, 0]
    T_BO_tup = [(t_gt, t_bo1), (t_bo1, t_bo2+t_bo1), (t_bo1+t_bo2, t_sim)]
    T_BO_arr = [t_bo1, t_bo1+t_bo2, t_sim]
    BETA = [beta1, beta2, 0]

    # initial conditions
    V_i = 0
    gam_i = np.pi/2
    X_i = 0
    H_i = 0
    G_T_bool = False
    Last_Stage_bool = False

    ## run simulation up to gravity turn
    print("\nStage 1")
    print("Time: ", 0)

    # Y = [V, gamma, X, H, mass]
    Y = [V_i, gam_i, X_i, H_i, M[0], 0, 0, 0]  # initial values for the rocket
    print("Y initital: ", Y)
    beta = BETA[0]
    t_bo = T_BO_arr[0]      # sets the Thrust to burn out at t_bo
    Isp = ISP[0]

    # solves the ODE up to the gravity turn
    hit_ground.terminal = True
    hit_ground.direction = -1
    solution = scip_int.solve_ivp(ascent, (0, t_gt), Y, method="RK45", max_step=0.1, events=hit_ground)

    # saves the data
    X_arr = (solution.y[2] / 1000)  # saves the current solutions position of the stages
    H_arr = (solution.y[3] / 1000)

    # saves the last values for the stage for the next one to start with
    V_i = solution.y[0][-1]
    gam_i = gam_g_t         # set the GT angle!
    X_i = solution.y[2][-1]
    H_i = solution.y[3][-1]
    M_i = solution.y[4][-1]
    t_i = solution.t[-1]
    V_gravity_i = solution.y[5][-1]
    V_drag_i = solution.y[6][-1]
    V_thrust_i = solution.y[7][-1]

    # Saves the new Y initial for the next stage
    Y = [V_i, gam_i, X_i, H_i, M_i, V_gravity_i, V_drag_i, V_thrust_i]
    print("Y initital: ", Y)
    V_drag_arr.append(V_drag_i)
    V_gravity_arr.append(V_gravity_i)
    V_thrust_arr.append(V_thrust_i)
    V_tot_arr.append(V_i)
    markers_pos.append([X_i, H_i])
    markers_time.append(t_i)
    print("gravity turn started!)")
    print("Time: ", t_i)
    G_T_bool = True

    # solves the ODE up to stage 1
    hit_ground.terminal = True
    hit_ground.direction = -1
    solution = scip_int.solve_ivp(ascent, T_BO_tup[0], Y, method="RK45", max_step=0.1, events=hit_ground)

    # saves the data
    X_arr = [*X_arr, *(solution.y[2] / 1000)]  # saves the current solutions position of the payload
    H_arr = [*H_arr, *(solution.y[3] / 1000)]

    # saves the last values for the stage for the next one to start with
    V_i = solution.y[0][-1]
    gam_i = solution.y[1][-1]
    X_i = solution.y[2][-1]
    H_i = solution.y[3][-1]
    M_i = solution.y[4][-1] - M_s[0] - mp1_retro
    t_i = solution.t[-1]
    V_gravity_i = solution.y[5][-1]
    V_drag_i = solution.y[6][-1]
    V_thrust_i = solution.y[7][-1]

    # Saves the new Y initial for the next stage
    Y = [V_i, gam_i, X_i, H_i, M_i, V_gravity_i, V_drag_i, V_thrust_i]
    V_drag_arr.append(V_drag_i)
    V_gravity_arr.append(V_gravity_i)
    V_thrust_arr.append(V_thrust_i)
    V_tot_arr.append(V_i)
    markers_pos.append([X_i, H_i])
    markers_time.append(t_i)

    for i in range(1, 3):
        """Runs the simulation for each stage, starting from stage 2, ending at payload"""
        # Y = [V, gamma, X, H, mass, V_gravity_i, V_drag_i, V_thrust_i]
        print("\nStage " + str(i+1) + " :")
        print("Time: ", t_i)
        beta = BETA[i]
        t_bo = T_BO_arr[i]
        Isp = ISP[i]

        if i == 1:
            # If last stage, start the steering law by setting these paramaters
            print("initiating steering law!")
            Last_Stage_bool = True
            gam_last_stage_i = gam_i
        elif i == 2:
            # stage 3 burnt out!
            # Now use the gam_dot equations
            print("Stage 2 burnt out, release the payload!")
            gam_i = 0
            Y = [V_i, gam_i, X_i, H_i, M_i, V_gravity_i, V_drag_i, V_thrust_i]
            Last_Stage_bool = False
        Y_i_arr.append(Y)
        # solves the ODE for the payload
        #print("Y initial: ", Y)
        hit_ground.terminal = True
        hit_ground.direction = -1
        sol_ascent = scip_int.solve_ivp(ascent, T_BO_tup[i], Y, method="RK45", max_step=0.1,  events=hit_ground)

        # saves the data
        X_arr = [*X_arr, *(sol_ascent.y[2]/1000)]                   # saves the current solutions position of the payload
        H_arr = [*H_arr, *(sol_ascent.y[3]/1000)]

        # saves the last values for the stage for the next one to start with
        V_i = sol_ascent.y[0][-1]
        gam_i = sol_ascent.y[1][-1]
        X_i = sol_ascent.y[2][-1]
        H_i = sol_ascent.y[3][-1]
        M_i = sol_ascent.y[4][-1] - M_s[i]
        t_i = sol_ascent.t[-1]
        V_gravity_i = sol_ascent.y[5][-1]
        V_drag_i = sol_ascent.y[6][-1]
        V_thrust_i = sol_ascent.y[7][-1]

        V_drag_arr.append(V_drag_i)
        V_gravity_arr.append(V_gravity_i)
        V_thrust_arr.append(V_thrust_i)
        V_tot_arr.append(V_i)
        markers_pos.append([X_i, H_i])
        markers_time.append(t_i)

        # Saves the new Y initial for the next stage
        Y = [V_i, gam_i, X_i, H_i, M_i, V_gravity_i, V_drag_i, V_thrust_i]


    print("Y_i_arr: ", Y_i_arr)
    # Calculates the re-entry trajectory of the stages
    calc_reentry(Y_i_arr, n_stages=2)

    V_drag = V_drag_arr[-1] / 1000
    V_gravity = V_gravity_arr[-1] / 1000
    V_thrust = V_thrust_arr[-1] / 1000

    print("\nSimulation finished!\n")
    print("Total rocket initial mass: ", m01)
    print("Velocity needed at orbit: ", V_c)
    print("Satellites initial velocity: ", (Y_i_arr[-1][0] - reverse_burn) / 1000)
    print("Velocity needed at reached orbit: ", np.sqrt(G * M_earth/(R_earth + Y_i_arr[-1][3]))/1000)
    print("")
    print("Satellites initial altitude: ", markers_pos[-2][1]/1000)

    print("Earth orbit velocity: ", V_earth)

    print("")
    print("Delta V_drag: ", V_drag)
    print("Delta V_gravity: ", V_gravity)
    print("Delta V_thrust: ", V_thrust)
    print("Delta V needed: ", (V_c - V_earth) - V_drag - V_gravity)
    print("Total delta V: ", V_drag - V_gravity - V_thrust)

    index_T = np.nonzero(T_arr_retro)[0][0]

    print("\nLanding 1st stage:")
    print("beta retro: ", beta_retro, "kg/s")
    print("propellant mass retro: ", mp1_retro, "kg")
    print("ms1: ", ms1, "kg\n")

    print("Seperation 1st stage: ", Time_arr_retro[0], "s")
    print("Retro booster starting time: ",round(Time_arr_retro[index_T],2), "s")
    print("Velicity booster starting: ",round(V_arr_retro[index_T],2), "km/s")
    print("Landing time: ", Time_arr_retro[-1], "s")
    print("Time retro booster acitvated: ", round(Time_arr_retro[-1] - Time_arr_retro[index_T],2))
    print("Landing velocity: ", V_arr_retro[-1]*3600, "km/h")
    print("Landing angle: ", gam_arr_retro[-1], "deg ")
    print("Landing mass: ", m_arr_retro[-1]*1000, "kg")
    print("Landing altitude: ", H_arr_retro[-1]*1000, "m")
    print("Propellant left: ", m_arr_retro[-1]*1000 - ms1, "kg" )

    # Plots
    SMALL_SIZE = 18
    MEDIUM_SIZE = 22
    BIGGER_SIZE = 32
    plt.rcParams.update({'mathtext.default': 'regular'})
    font = {'family': 'normal', 'weight': 'bold'}
    plt.rc('font', **font)
    plt.rc('font', size=MEDIUM_SIZE)  # controls default text sizes
    plt.rc('axes', titlesize=BIGGER_SIZE)  # fontsize of the axes title
    plt.rc('axes', labelsize=MEDIUM_SIZE)  # fontsize of the x and y labels
    plt.rc('xtick', labelsize=SMALL_SIZE)  # fontsize of the tick labels
    plt.rc('ytick', labelsize=SMALL_SIZE)  # fontsize of the tick labels
    plt.rc('legend', fontsize=SMALL_SIZE)  # legend fontsize
    plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title

    fig, ax = plt.subplots()
    trajectory_ascent, = ax.plot(X_arr, H_arr, 'r', linewidth=2.0)
    trajectory_reentry_s1, = ax.plot(X_arr_re[0], H_arr_re[0], 'b-.', linewidth=2.0)
    trajectory_reentry_s2, = ax.plot(X_arr_re[1], H_arr_re[1], 'b:', linewidth=2.0)

    G_turn, = ax.plot(markers_pos[0][0] / 1000, markers_pos[0][1] / 1000, color='g', marker="^", markersize=14)  # plots the gravity turn point
    stage1_bo_p, = ax.plot(markers_pos[1][0] / 1000, markers_pos[1][1] / 1000, color='g',
                           marker="X", markersize=14, linewidth=2.0)  # plots the gravity turn point
    stage2_bo_p, = ax.plot(markers_pos[2][0] / 1000, markers_pos[2][1] / 1000, color='g',
                           marker="P", markersize=14, linewidth=2.0)  # plots the gravity turn point
    plt.xlabel("Ground range [km]", fontweight='bold')
    plt.ylabel("Altitude [km]", fontweight='bold')
    plt.title("Trajectories of the RLV", fontweight='bold')
    ax.legend((G_turn, stage1_bo_p, stage2_bo_p, trajectory_ascent, trajectory_reentry_s1, trajectory_reentry_s2),
              ("Gravity turn", "Stage 1 burnout", "Stage 2 burnout", "Ascent", "Reentry stage 1", "Reentry stage 2"), loc='right')
    props = dict(boxstyle='round', alpha=0.5, facecolor='wheat')

    text_1 = '\n'.join(("Gravity turn:    Payload initial orbit: ",
                        r'$\gamma_0$: ' + str(
                            round(gam_g_t * 180 / np.pi, 2)) + '$^\circ$             $H_{payload}$: ' + str(
                            round(Y_i_arr[-1][3] / 1000, 2)) + " km",
                        '$H_{0}$: ' + str(round(markers_pos[0][1] / 1000, 2)) + " km         $V_{payload}$: " + str(
                            round((Y_i_arr[-1][0] - reverse_burn) / 1000, 2)) + " km/s  "))

    plt.text(0.95, 0.9, text_1, transform=ax.transAxes, verticalalignment='top',
             horizontalalignment='right', bbox=props)

    # plots the forces on the rocket (ascent)
    plt.figure()
    plt.subplot(4, 1, 1)
    plt.title('Forces during ascent - reusable rocket', fontsize='large', fontweight='bold')
    plt.ylabel('Thrust [kN]', fontsize='large', fontweight='bold')
    plt.plot(markers_time[0], T_arr[Time_arr.index(markers_time[0])], 'r<', label="Gravity turn")
    plt.plot(markers_time[1], T_arr[Time_arr.index(markers_time[1])], 'rP', label="Stage 1")
    plt.plot(markers_time[2], T_arr[Time_arr.index(markers_time[2])], 'rX', label="Stage 2")
    plt.legend(framealpha=1, frameon=True)
    plt.plot(Time_arr, T_arr)
    plt.subplot(4, 1, 2)
    plt.plot(Time_arr, D_arr)
    plt.ylabel('Drag [kN]', fontweight='bold')
    plt.subplot(4, 1, 3)
    plt.plot(Time_arr, g_arr)
    plt.ylabel('g/g0', fontweight='bold')
    plt.subplot(4, 1, 4)
    plt.plot(Time_arr, mass_arr)
    plt.ylabel('Mass [ton]', fontweight='bold')
    plt.xlabel('Time [s]', fontweight='bold')

    # plots the rockets position and velocity
    plt.figure()
    plt.subplot(3, 1, 1)
    plt.title('Ascent data - reusable rocket', fontweight='bold')
    plt.ylabel('Height [km]',  fontweight='bold')
    plt.plot(markers_time[0], markers_pos[0][1] / 1000, 'r<', label="Gravity turn")
    plt.plot(markers_time[1], markers_pos[1][1] / 1000, 'rP', label="Stage 2")
    plt.plot(markers_time[2], markers_pos[2][1] / 1000, 'rX', label="Payload")
    plt.legend(framealpha=1, frameon=True)
    plt.plot(Time_arr, H_arr_plot)
    plt.subplot(3, 1, 2)
    plt.plot(Time_arr, V_arr)
    V_c_arr = np.full((len(Time_arr)), V_c)
    plt.plot(Time_arr, V_c_arr, 'r--')
    plt.ylabel('V [km/s]',  fontweight='bold')
    plt.subplot(3, 1, 3)
    plt.plot(Time_arr, gam_arr)
    plt.ylabel('Gamma [deg]', fontweight='bold')
    #plt.subplot(4, 1, 4)
    #plt.plot(Time_arr, gam_dot_arr)
    #plt.ylabel('Gamma_dot [deg/s]', fontsize='large', fontweight='bold')
    plt.xlabel('Time [s]', fontweight='bold')

    # Re-entry plots
    plt.figure()
    plt.subplot(2, 1, 1)
    plt.title('Heat generated during decent for the RLV stages', fontweight='bold')
    print("Q_arr_re: ", Q_arr_re)
    plt.plot(Q_arr_re[0][1], H_arr_re[0][Q_arr_re[0][0]:],
             label="Stage 1\n$Q_{tot}$ = " + str(round(Q_arr_re[0][2], 2)) + "MJ\n$\Delta$T = " + str(
                 round(1000000 * Q_arr_re[0][2] / (Csteel * ms1), 2)) + 'K$^\circ$')
    plt.legend(framealpha=1, frameon=True, loc="upper right")
    plt.subplot(2, 1, 2)
    plt.ylabel("Altitude [km]", fontweight='bold')
    plt.plot(Q_arr_re[1][1], H_arr_re[1][Q_arr_re[1][0]:],
             label="Stage 2\n$Q_{tot}$ = " + str(round(Q_arr_re[1][2], 2)) + "MJ\n$\Delta$T = " + str(
                 round(1000000 * Q_arr_re[1][2] / (Csteel * ms2), 2)) + 'K$^\circ$')
    plt.legend(framealpha=1, frameon=True, loc="lower right")
    plt.xlabel("Heating rate [W/cm^2]", fontweight='bold')
    plt.figure()
    plt.title('Reentry - reusable 1st stage',  fontweight='bold')
    plt.plot(X_arr_retro, H_arr_retro)
    #plt.plot(markers_time[1], markers_pos[1][1] / 1000, 'rP', label="Stage 1 burn out")
    #plt.plot(Time_arr_retro[index_T], H_arr_retro[index_T], 'gX', label="Retro booster acitvated")
    #H_atmos_start = np.full((len(Time_arr_retro)), 80)
    #H_atmos = np.full((len(Time_arr_retro)), 30)
    #ground = np.full((len(Time_arr_retro)), 0)
    #plt.plot(Time_arr_retro, H_atmos_start, 'r--', label="Start of atmosphere (80 km)")
    #plt.plot(Time_arr_retro, H_atmos, 'r:', label="Atmosphere (20 km)")
    #plt.plot(Time_arr_retro, ground, 'g')
    plt.ylabel('Altitude [km]',  fontweight='bold')
    plt.xlabel("Ground range [km]",  fontweight='bold')
    plt.legend(framealpha=1, frameon=True)

    plt.figure()
    plt.subplot(3, 1, 1)
    plt.title('Reentry - reusable 1st stage',  fontweight='bold')
    plt.plot(Time_arr_retro, V_arr_retro)
    plt.ylabel('V [km/s]',  fontweight='bold')
    plt.subplot(3, 1, 2)
    plt.ylabel('Thrust [kN]', fontweight='bold')
    plt.plot(Time_arr_retro, T_arr_retro)
    plt.subplot(3, 1, 3)
    ms1_f = np.full((len(Time_arr_retro)), ms1/1000)
    plt.plot(Time_arr_retro, m_arr_retro)
    plt.plot(Time_arr_retro, ms1_f, 'r:', label="Structure mass stage 1")
    plt.ylabel('Mass [tons]',  fontweight='bold')
    plt.xlabel('Time [s]',  fontweight='bold')
    plt.legend(framealpha=1, frameon=True, loc="left")

    plt.figure()
    plt.subplot(2, 1, 1)
    plt.title('1st stage re-entry', fontweight='bold')
    plt.plot(V_arr_retro, H_arr_retro)
    plt.ylabel('H [km]', fontweight='bold')
    plt.xlabel('V [km/s]', fontweight='bold')
    plt.legend(framealpha=1, frameon=True)
    plt.subplot(2, 1, 2)
    plt.plot(Time_arr_retro, gam_arr_retro, '.')
    plt.ylabel('Gamma [deg]', fontweight='bold')
    plt.xlabel('Time [s]', fontweight='bold')
    plt.show()